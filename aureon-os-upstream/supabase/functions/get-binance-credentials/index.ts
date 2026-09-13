// Retired security boundary.
//
// This legacy endpoint decrypted a user's Binance key pair and returned both
// plaintext values to its caller. A browser-accessible Edge Function must
// never export reusable exchange credentials, even to the credential owner.
// Server-side portfolio and health functions now decrypt only inside their own
// invocation and use the values for the one provider request.

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve((request) => {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  return new Response(
    JSON.stringify({
      error: "CREDENTIAL_EXPORT_RETIRED",
      message: "Exchange credentials are used only inside server-side provider operations.",
    }),
    {
      status: 410,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    },
  );
});
