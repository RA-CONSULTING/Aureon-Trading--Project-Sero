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
      error: 'PRIVILEGED_HEALTH_CHECK_DISABLED',
      route: 'backend-health-check',
      requiredPath: 'governed_operator_health',
      truthStatus: 'no_data',
      readState: 'unavailable',
      mutationAuthority: false,
      providerCallsAttempted: 0,
      secretPresenceDisclosed: false,
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
