import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { Resend } from "https://esm.sh/resend@2.0.0";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface HealthAlertRequest {
  email: string;
  severity: 'warning' | 'error' | 'info';
  title: string;
  message: string;
  healthReport?: any;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const resendApiKey = Deno.env.get('RESEND_API_KEY');
    
    if (!resendApiKey) {
      throw new Error('RESEND_API_KEY not configured');
    }

    const resend = new Resend(resendApiKey);
    const { email, severity, title, message, healthReport }: HealthAlertRequest = await req.json();

    console.log('[send-health-alert] Sending alert email:', { email, severity, title });

    // Determine email styling based on severity
    const severityColors = {
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6',
    };

    const severityIcons = {
      error: '🚨',
      warning: '⚠️',
      info: 'ℹ️',
    };

    const color = severityColors[severity];
    const icon = severityIcons[severity];

    // Build detailed health report HTML if provided
    let healthDetailsHtml = '';
    if (healthReport) {
      healthDetailsHtml = `
        <div style="margin-top: 20px; padding: 15px; background-color: #f9fafb; border-radius: 8px;">
          <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #374151;">System Details</h3>
          <ul style="margin: 0; padding-left: 20px; color: #6b7280;">
            <li><strong>Overall Status:</strong> ${healthReport.overall_status}</li>
            <li><strong>Timestamp:</strong> ${new Date(healthReport.timestamp).toLocaleString()}</li>
            ${healthReport.errors?.length > 0 ? `<li><strong>Errors:</strong> ${healthReport.errors.join(', ')}</li>` : ''}
            ${healthReport.warnings?.length > 0 ? `<li><strong>Warnings:</strong> ${healthReport.warnings.join(', ')}</li>` : ''}
          </ul>
        </div>
      `;
    }

    const emailHtml = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>${title}</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0; background-color: #f3f4f6;">
          <div style="max-width: 600px; margin: 40px auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, ${color} 0%, ${color}dd 100%); padding: 30px; text-align: center;">
              <div style="font-size: 48px; margin-bottom: 10px;">${icon}</div>
              <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">Backend Health Alert</h1>
            </div>
            
            <!-- Content -->
            <div style="padding: 30px;">
              <div style="background-color: #fef3c7; border-left: 4px solid ${color}; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #92400e;">${title}</h2>
                <p style="margin: 0; color: #78350f; line-height: 1.5;">${message}</p>
              </div>
              
              ${healthDetailsHtml}
              
              <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                  This is an automated alert from your AUREON Quantum Trading System backend health monitoring service.
                </p>
                <p style="margin: 10px 0 0 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                  To review your system health, please log in to your dashboard.
                </p>
              </div>
            </div>
            
            <!-- Footer -->
            <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
              <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                © ${new Date().getFullYear()} AUREON. All rights reserved.
              </p>
            </div>
          </div>
        </body>
      </html>
    `;

    const emailResponse = await resend.emails.send({
      from: 'AUREON Health Monitor <alerts@resend.dev>',
      to: [email],
      subject: `${icon} ${title}`,
      html: emailHtml,
    });

    console.log('[send-health-alert] Email sent successfully:', emailResponse);

    return new Response(
      JSON.stringify({ success: true, response: emailResponse }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error) {
    console.error('[send-health-alert] Error:', error);
    
    return new Response(
      JSON.stringify({
        error: error instanceof Error ? error.message : 'Failed to send alert',
      }),
      {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
