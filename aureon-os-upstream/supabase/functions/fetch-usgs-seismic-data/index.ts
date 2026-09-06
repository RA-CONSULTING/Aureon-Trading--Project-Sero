import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface EarthquakeEvent {
  id: string;
  magnitude: number;
  location: string;
  depth: number;
  timestamp: string;
  latitude: number;
  longitude: number;
  significance: number;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    console.log('[fetch-usgs-seismic-data] Fetching USGS earthquake data');

    const USGS_API_KEY = Deno.env.get('USGS_API_KEY');
    
    // Fetch significant earthquakes from last 7 days
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const startTime = sevenDaysAgo.toISOString().split('T')[0];

    const url = `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=${startTime}&minmagnitude=4.0&orderby=time`;
    
    const response = await fetch(url, {
      headers: USGS_API_KEY ? { 'Authorization': `Bearer ${USGS_API_KEY}` } : {}
    });

    if (!response.ok) {
      throw new Error(`USGS API error: ${response.status}`);
    }

    const data = await response.json();
    
    // Parse earthquake events
    const earthquakes: EarthquakeEvent[] = data.features.map((feature: any) => ({
      id: feature.id,
      magnitude: feature.properties.mag,
      location: feature.properties.place,
      depth: feature.geometry.coordinates[2],
      timestamp: new Date(feature.properties.time).toISOString(),
      latitude: feature.geometry.coordinates[1],
      longitude: feature.geometry.coordinates[0],
      significance: feature.properties.sig || 0,
    }));

    // Calculate seismic activity metrics
    const totalEvents = earthquakes.length;
    const significantEvents = earthquakes.filter(e => e.magnitude >= 5.0).length;
    const majorEvents = earthquakes.filter(e => e.magnitude >= 6.0).length;
    const avgMagnitude = earthquakes.reduce((sum, e) => sum + e.magnitude, 0) / totalEvents || 0;
    const avgDepth = earthquakes.reduce((sum, e) => sum + e.depth, 0) / totalEvents || 0;

    // Calculate seismic energy release (simplified)
    const totalEnergy = earthquakes.reduce((sum, e) => {
      // Simplified energy calculation: E = 10^(1.5*M + 4.8)
      return sum + Math.pow(10, 1.5 * e.magnitude + 4.8);
    }, 0);

    // Detect patterns
    const recentEvents = earthquakes.slice(0, 10);
    const last24h = earthquakes.filter(e => 
      new Date(e.timestamp).getTime() > Date.now() - 24 * 60 * 60 * 1000
    );

    // Calculate seismic stability index (0-1, higher = more stable)
    const stabilityIndex = Math.max(0, 1 - (significantEvents / 10));

    // Detect clusters (events within 500km and 24h)
    const clusters = [];
    for (let i = 0; i < earthquakes.length; i++) {
      const cluster = [earthquakes[i]];
      for (let j = i + 1; j < earthquakes.length; j++) {
        const distance = calculateDistance(
          earthquakes[i].latitude, earthquakes[i].longitude,
          earthquakes[j].latitude, earthquakes[j].longitude
        );
        const timeDiff = Math.abs(
          new Date(earthquakes[i].timestamp).getTime() - 
          new Date(earthquakes[j].timestamp).getTime()
        );
        if (distance < 500 && timeDiff < 24 * 60 * 60 * 1000) {
          cluster.push(earthquakes[j]);
        }
      }
      if (cluster.length >= 3) {
        clusters.push({
          center: {
            lat: cluster.reduce((s, e) => s + e.latitude, 0) / cluster.length,
            lon: cluster.reduce((s, e) => s + e.longitude, 0) / cluster.length,
          },
          count: cluster.length,
          avgMagnitude: cluster.reduce((s, e) => s + e.magnitude, 0) / cluster.length,
        });
      }
    }

    const responseData = {
      timestamp: new Date().toISOString(),
      events: recentEvents,
      allEvents: earthquakes,
      statistics: {
        totalEvents,
        significantEvents,
        majorEvents,
        avgMagnitude,
        avgDepth,
        totalEnergy,
        stabilityIndex,
        last24hCount: last24h.length,
      },
      clusters,
      alerts: {
        highActivity: last24h.length > 5,
        majorEvent: majorEvents > 0,
        clusterDetected: clusters.length > 0,
      },
      activityLevel: 
        majorEvents > 0 ? 'EXTREME' :
        significantEvents > 3 ? 'HIGH' :
        significantEvents > 1 ? 'MODERATE' :
        'QUIET',
    };

    console.log('[fetch-usgs-seismic-data] Data fetched successfully');

    return new Response(JSON.stringify(responseData), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('[fetch-usgs-seismic-data] Error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
    return new Response(
      JSON.stringify({ error: errorMessage }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});

// Calculate distance between two points using Haversine formula (in km)
function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}
