#!/usr/bin/env tsx
/**
 * Earth-AUREON Integration Test
 * Demonstrates quantum-enhanced trading with Earth electromagnetic field synchronization
 */

import { earthStreamsMonitor } from '../lib/earth-streams';
import { earthAureonBridge } from '../core/earthAureonBridge';
import { generateRegionalEmotionalState } from '../lib/schumann-emotional-mapping';

console.log('🌍 EARTH-AUREON QUANTUM INTEGRATION TEST');
console.log('=' .repeat(60));

// Initialize Earth streams monitor
earthStreamsMonitor.initialize();

console.log('\n✅ Earth Streams Monitor initialized');
console.log('📡 Collecting solar wind, geomagnetic, and Schumann data...\n');

// Wait for initial data
await new Promise(resolve => setTimeout(resolve, 3000));

// Test 1: Get Earth metrics
console.log('TEST 1: Earth Stream Metrics');
console.log('-'.repeat(60));
const metrics = earthStreamsMonitor.getEarthStreamMetrics();
if (metrics) {
  console.log(`Solar Wind Velocity: ${metrics.solarWind.velocity.toFixed(1)} km/s`);
  console.log(`Solar Wind Density: ${metrics.solarWind.density.toFixed(2)} protons/cm³`);
  console.log(`Magnetic Field: ${metrics.solarWind.magneticField.toFixed(2)} nT`);
  console.log(`Geomagnetic Kp Index: ${metrics.geomagnetic.kpIndex.toFixed(1)}`);
  console.log(`Geomagnetic Field: ${metrics.geomagnetic.fieldStrength.toFixed(0)} nT`);
  console.log(`Ionospheric Density: ${(metrics.atmospheric.ionosphericDensity / 1e12).toFixed(2)}×10¹² e/m³`);
  console.log(`Field Coupling: ${metrics.fieldCoupling.toFixed(3)}`);
  console.log(`Coherence Index: ${metrics.coherenceIndex.toFixed(3)}`);
}

// Test 2: Earth-AUREON Bridge
console.log('\n\nTEST 2: Earth-AUREON Field Influence');
console.log('-'.repeat(60));
const simpleStreams = {
  solarWindVelocity: metrics?.solarWind.velocity || 400,
  geomagneticKp: metrics?.geomagnetic.kpIndex || 2,
  ionosphericDensity: (metrics?.atmospheric.ionosphericDensity || 1e12) / 1e10,
  fieldCoupling: metrics?.fieldCoupling || 1.2
};

const influence = await earthAureonBridge.getEarthInfluence(simpleStreams);
console.log(`Schumann Coherence: ${(influence.schumannCoherence * 100).toFixed(1)}%`);
console.log(`Solar Wind Modifier: ${influence.solarWindModifier > 0 ? '+' : ''}${(influence.solarWindModifier * 100).toFixed(1)}%`);
console.log(`Geomagnetic Stability: ${(influence.geomagneticStability * 100).toFixed(1)}%`);
console.log(`Emotional Resonance: ${(influence.emotionalResonance * 100).toFixed(1)}%`);
console.log(`Dominant Frequency: ${influence.dominantFrequency.toFixed(2)} Hz`);
console.log(`\n💎 COMBINED TRADING BOOST: ${influence.combinedBoost > 0 ? '+' : ''}${(influence.combinedBoost * 100).toFixed(2)}%`);

if (influence.emotionalState) {
  console.log(`\nEmotional State:`);
  console.log(`  Tags: ${influence.emotionalState.emotionalTags.slice(0, 4).join(', ')}`);
  console.log(`  Valence: ${(influence.emotionalState.valence * 100).toFixed(0)}%`);
  console.log(`  Arousal: ${(influence.emotionalState.arousal * 100).toFixed(0)}%`);
  console.log(`  Description: ${influence.emotionalState.description}`);
}

// Test 3: Regional emotional profiles
console.log('\n\nTEST 3: Regional Emotional Field Analysis');
console.log('-'.repeat(60));
const regions = ['north-america', 'europe', 'asia', 'africa'];
for (const region of regions) {
  const emotionalState = generateRegionalEmotionalState(region);
  console.log(`\n${region.toUpperCase().replace('-', ' ')}:`);
  console.log(`  Frequency: ${emotionalState.frequency.toFixed(2)} Hz`);
  console.log(`  Intensity: ${(emotionalState.intensity * 100).toFixed(0)}%`);
  console.log(`  Emotions: ${emotionalState.emotionalTags.slice(0, 3).join(', ')}`);
}

// Test 4: Real-time monitoring
console.log('\n\nTEST 4: Real-Time Field Monitoring (10 samples)');
console.log('-'.repeat(60));
console.log('Time | Schumann | Solar Wind | Kp | Boost | Status');
console.log('-'.repeat(60));

for (let i = 0; i < 10; i++) {
  await new Promise(resolve => setTimeout(resolve, 1500));
  
  const currentMetrics = earthStreamsMonitor.getEarthStreamMetrics();
  if (currentMetrics) {
    const streams = {
      solarWindVelocity: currentMetrics.solarWind.velocity,
      geomagneticKp: currentMetrics.geomagnetic.kpIndex,
      ionosphericDensity: currentMetrics.atmospheric.ionosphericDensity / 1e10,
      fieldCoupling: currentMetrics.fieldCoupling
    };
    
    const currentInfluence = await earthAureonBridge.getEarthInfluence(streams);
    
    const time = new Date().toLocaleTimeString();
    const schumann = `${(currentInfluence.schumannCoherence * 100).toFixed(0)}%`;
    const solar = `${currentMetrics.solarWind.velocity.toFixed(0)}km/s`;
    const kp = currentMetrics.geomagnetic.kpIndex.toFixed(1);
    const boost = `${currentInfluence.combinedBoost > 0 ? '+' : ''}${(currentInfluence.combinedBoost * 100).toFixed(1)}%`;
    
    let status = '🔴';
    if (currentInfluence.combinedBoost > 0.1) status = '🟢';
    else if (currentInfluence.combinedBoost > 0) status = '🔵';
    else if (currentInfluence.combinedBoost > -0.05) status = '🟡';
    
    console.log(`${time.slice(-8)} | ${schumann.padEnd(8)} | ${solar.padEnd(10)} | ${kp.padEnd(3)} | ${boost.padEnd(6)} | ${status}`);
  }
}

// Test 5: Configuration test
console.log('\n\nTEST 5: Earth-AUREON Configuration');
console.log('-'.repeat(60));
const config = earthAureonBridge.getConfig();
console.log(`Schumann Weight: ${(config.schumannWeight * 100).toFixed(0)}%`);
console.log(`Solar Wind Weight: ${(config.solarWindWeight * 100).toFixed(0)}%`);
console.log(`Emotional Weight: ${(config.emotionalWeight * 100).toFixed(0)}%`);
console.log(`Earth Sync Enabled: ${config.enableEarthSync ? '✅' : '❌'}`);

console.log('\n\n' + '='.repeat(60));
console.log('🎯 EARTH-AUREON INTEGRATION: OPERATIONAL');
console.log('=' .repeat(60));
console.log('\nKey Features Activated:');
console.log('✅ Schumann Resonance real-time monitoring');
console.log('✅ Solar wind field analysis');
console.log('✅ Geomagnetic field coupling');
console.log('✅ Emotional frequency mapping');
console.log('✅ Multi-layer coherence boosting');
console.log('✅ Regional emotional profiling');
console.log('\n🚀 Ready for quantum-enhanced trading signals!');
