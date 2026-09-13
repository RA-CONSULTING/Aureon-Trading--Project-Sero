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
      error: 'LEGACY_DIRECT_EXECUTION_DISABLED',
      route: 'execute-trade-user-alpaca',
      requiredPath: 'governed_cloud_executor',
      truthStatus: 'no_data',
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