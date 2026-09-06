"""Verify or restore the complete Aureon workspace without executing its code.

Requires: Python 3.10+, cryptography; pywin32 for a Windows DPAPI recovery key.
The default operation verifies authenticated encryption and every archived file.
"""
from pathlib import Path, PurePosixPath
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import argparse, base64, bisect, hashlib, io, json, os, zipfile


class DecryptedZip(io.RawIOBase):
    """Seekable CTR view, used ONLY after the complete GCM tag is verified."""
    def __init__(self, directory, manifest, key):
        self.paths=[directory/p['file'] for p in manifest['parts']]
        self.ends=[]; self.length=0
        for p in manifest['parts']:
            self.length+=p['bytes']; self.ends.append(self.length)
        self.key=key; self.nonce=bytes.fromhex(manifest['nonce_hex']); self.pos=0
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.length+offset
        if self.pos<0: raise ValueError('Negative seek')
        return self.pos
    def read(self, size=-1):
        size=max(0,self.length-self.pos) if size<0 else min(size,max(0,self.length-self.pos))
        if not size: return b''
        start=self.pos; blocks=[]; remaining=size
        while remaining:
            index=bisect.bisect_right(self.ends,self.pos)
            previous=self.ends[index-1] if index else 0
            count=min(remaining,self.ends[index]-self.pos)
            with self.paths[index].open('rb') as f:
                f.seek(self.pos-previous); block=f.read(count)
            if len(block)!=count: raise IOError('Truncated backup part')
            blocks.append(block);self.pos+=count;remaining-=count
        block_index,skip=divmod(start,16)
        counter=self.nonce+(block_index+2).to_bytes(4,'big')
        dec=Cipher(algorithms.AES(self.key),modes.CTR(counter)).decryptor()
        if skip: dec.update(b'\x00'*skip)
        return dec.update(b''.join(blocks))+dec.finalize()


def load_key(path):
    data=path.read_bytes()
    if path.suffix.lower()=='.dpapi':
        import win32crypt
        return win32crypt.CryptUnprotectData(data,None,None,None,0)[1]
    key=base64.b64decode(data.strip(),validate=True)
    if len(key)!=32: raise ValueError('Expected a base64 encoded 32-byte recovery key')
    return key


def authenticate(directory,manifest,key):
    dec=Cipher(algorithms.AES(key),modes.GCM(bytes.fromhex(manifest['nonce_hex']),bytes.fromhex(manifest['tag_hex']))).decryptor()
    dec.authenticate_additional_data(manifest['aad'].encode())
    overall=hashlib.sha256()
    for part in manifest['parts']:
        p=(directory/part['file']).resolve()
        if p.parent!=directory.resolve(): raise ValueError('Unsafe part filename')
        h=hashlib.sha256(); total=0
        with p.open('rb') as f:
            while data:=f.read(4*1024*1024):
                h.update(data);overall.update(data);total+=len(data);dec.update(data)
        if total!=part['bytes'] or h.hexdigest()!=part['sha256']: raise ValueError('Backup part checksum failed: '+part['file'])
    dec.finalize()
    if overall.hexdigest()!=manifest['ciphertext_sha256']: raise ValueError('Ciphertext checksum failed')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--backup',type=Path,required=True,help='full-workspace-backup directory from the GitHub clone')
    ap.add_argument('--key-file',type=Path,required=True,help='local DPAPI file or a portable base64 key file')
    ap.add_argument('--restore',type=Path,help='new empty destination; omit to verify only')
    ap.add_argument('--export-key',type=Path,help='write a portable recovery key locally; never upload it to GitHub')
    args=ap.parse_args(); key=load_key(args.key_file)
    manifest=json.loads((args.backup/'backup-manifest.json').read_text(encoding='utf-8'))
    authenticate(args.backup,manifest,key)
    reader=DecryptedZip(args.backup,manifest,key)
    restored=0; checked=0; checked_bytes=0
    with zipfile.ZipFile(reader) as archive:
        original=json.loads(archive.read('snapshot-manifest.json'))
        expected={r['path']:r for r in original['files']}
        if args.restore:
            root=args.restore.resolve()
            if root.exists() and any(root.iterdir()): raise ValueError('Restore destination must be empty')
            root.mkdir(parents=True,exist_ok=True)
        for info in archive.infolist():
            if not info.filename.startswith('workspace/'): continue
            rel=PurePosixPath(info.filename).relative_to('workspace')
            if rel.is_absolute() or '..' in rel.parts or any(':' in p for p in rel.parts): raise ValueError('Unsafe archive path')
            if info.is_dir():
                if args.restore: root.joinpath(*rel.parts).mkdir(parents=True,exist_ok=True)
                continue
            row=expected.get(rel.as_posix())
            if row is None: raise ValueError('Unexpected archive file')
            digest=hashlib.sha256(); count=0; output=None
            if args.restore:
                dest=root.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists(): raise FileExistsError('Refusing to overwrite: '+str(rel))
                output=dest.open('xb')
            try:
                with archive.open(info) as src:
                    while data:=src.read(1024*1024):
                        digest.update(data);count+=len(data)
                        if output: output.write(data)
            finally:
                if output: output.close()
            if count!=row['bytes'] or digest.hexdigest()!=row['sha256']: raise ValueError('Archived file verification failed: '+str(rel))
            if args.restore:
                os.utime(dest,ns=(row['mtime_ns'],row['mtime_ns']));restored+=1
            checked+=1;checked_bytes+=count
        if checked!=len(expected): raise ValueError('Archive file count mismatch')
    if args.export_key:
        if args.export_key.exists(): raise FileExistsError('Recovery key destination already exists')
        fd=os.open(args.export_key,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f: f.write(base64.b64encode(key)+b'\n')
    print(json.dumps({'authenticated':True,'verified_files':checked,'verified_bytes':checked_bytes,'restored_files':restored,
                      'unavailable_files':original['unavailable'],'live_files_changed_during_read':len(original['changed_during_read'])},indent=2))


if __name__=='__main__': main()
