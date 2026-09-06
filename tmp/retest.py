import re
c = r'C:\Users\user\.kimi_openclaw\workspace\real_time_data_feeder.py'
c2 = c + ' --interval 300'
pats = {
    'trailing_class_end': r'(?:^|[/"\s])real_time_data_feeder\.py(?:[/"\s]|$)',
    'plain': r'real_time_data_feeder\.py',
    'class_only': r'[/"\s]real_time_data_feeder\.py$',
}
for name, p in pats.items():
    print(name, 'c:', bool(re.search(p, c)), '| c2:', bool(re.search(p, c2)))
print('class check:', repr(re.search(r'[/"\s]', 'x y').group(0)))
