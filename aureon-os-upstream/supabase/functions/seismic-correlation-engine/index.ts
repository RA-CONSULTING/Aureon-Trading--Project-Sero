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
      error: 'LEGACY_GLOBAL_PRIVILEGED_ROUTE_DISABLED',
      route: 'seismic-correlation-engine',
      requiredPath: 'identity_bound_operator_or_tenant_runtime',
      truthStatus: 'no_data',
      mutationAuthority: false,
      providerCallsAttempted: 0,
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
