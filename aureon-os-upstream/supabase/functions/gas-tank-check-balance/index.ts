const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve((req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  return new Response(
    JSON.stringify({
      success: false,
      error: 'PRIVILEGED_BALANCE_LOOKUP_DISABLED',
      route: 'gas-tank-check-balance',
      requiredPath: 'authenticated_rls_account_read',
      balanceDisclosed: false,
      serviceRoleUsed: false,
      generatedValues: false,
    }),
    {
      status: 503,
      headers: {
        ...corsHeaders,
        'Cache-Control': 'no-store',
        'Content-Type': 'application/json',
      },
    },
  );
});
