/**
 * 🦆⚔️ DUCK COMMANDOS - THE ELITE SQUAD ⚔️🦆
 * ============================================
 * 
 * THE ORIGIN STORY:
 * Duck Hunt was rigged - the British elite system hunting Irish digital ducks for sport.
 * One duck escaped - QUANTUM QUACKERS - who vowed never to let the system fuck him over again.
 * 
 * He rose an elite squad of Duck Commandos - one from each of the Four Provinces of Ireland.
 * Each commando took on ONE trading platform. They became elite 1 penny net profit crypto snipers.
 * Every kill counts. Every trade is precise. Death by a thousand cuts to the system that hunted them.
 * 
 * "They thought they were hunting ducks. They didn't know they were creating soldiers."
 * 
 * THE MISSION: Reclaim every penny. Stack the bread. Never let the system win again.
 */

export type Province = 'Ulster' | 'Munster' | 'Leinster' | 'Connacht';
export type Exchange = 'kraken' | 'binance' | 'alpaca' | 'capital';

export interface DuckCommando {
  codename: string;
  realName: string;
  nickname: string;
  province: Province;
  provinceEmoji: string;
  provinceColor: string;
  exchange: Exchange;
  exchangeEmoji: string;
  personality: string;
  backstory: string;
  avatar: string;
  killQuotes: string[];
  missionQuotes: string[];
}

// 🦆 THE ELITE SQUAD - FOUR PROVINCES, FOUR EXCHANGES, ONE MISSION 🦆

export const DUCK_COMMANDOS: Record<Exchange, DuckCommando> = {
  kraken: {
    codename: 'ULSTER-1',
    realName: 'Seamus O\'Quack',
    nickname: 'The Silent',
    province: 'Ulster',
    provinceEmoji: '🟢',
    provinceColor: '#169B62', // Irish green
    exchange: 'kraken',
    exchangeEmoji: '🐙',
    personality: 'Cold, precise, veteran of the Falls Road',
    backstory: 'Born in the shadows of Belfast, Seamus watched his family hunted during Duck Hunt. He escaped through the sewers of Divis Flats, learning to strike silent and unseen.',
    avatar: '🦆',
    killQuotes: [
      "From the shadows of Belfast, another target eliminated.",
      "The Falls Road remembers. The Falls Road strikes.",
      "Silent as the Lagan at midnight.",
      "They'll never see the next one coming either.",
      "For every duck they hunted, we take a thousand pennies.",
      "The murals on our walls tell of victories like this.",
      "Cold and calculated. Just like the Belfast rain.",
      "Another one for the books, another one for Ulster.",
    ],
    missionQuotes: [
      "Eyes on the Kraken depths. Waiting for the moment.",
      "The sea creature stirs. We stir with it.",
      "Belfast didn't raise quitters.",
    ],
  },
  
  binance: {
    codename: 'MUNSTER-1',
    realName: 'Padraig McFlapper',
    nickname: 'Penny',
    province: 'Munster',
    provinceEmoji: '🟡',
    provinceColor: '#FFD700', // Gold
    exchange: 'binance',
    exchangeEmoji: '🟡',
    personality: 'Fast-talking Cork duck, counts every cent',
    backstory: 'From the rebel county of Cork, Padraig learned that every penny counts. While others chased big scores, he perfected the art of the small win. Stack enough pennies and you\'ve got a war chest.',
    avatar: '🦆',
    killQuotes: [
      "Every penny for the cause! Cork remembers!",
      "Stack the bread, one cent at a time, boy!",
      "The Rebel County strikes again!",
      "Sure look, another penny in the pocket!",
      "They laughed at my pennies. Now who's counting?",
      "From the banks of the Lee to your wallet!",
      "Cork said it couldn't be done. Cork was wrong!",
      "A penny here, a penny there - empire falls!",
    ],
    missionQuotes: [
      "Binance is buzzing. The Munster duck is ready.",
      "Count the coins, count the victories.",
      "Cork ducks don't miss twice.",
    ],
  },
  
  alpaca: {
    codename: 'LEINSTER-1',
    realName: 'Fionnuala Feather',
    nickname: 'The Fox',
    province: 'Leinster',
    provinceEmoji: '🔵',
    provinceColor: '#0066CC', // Dublin blue
    exchange: 'alpaca',
    exchangeEmoji: '🦙',
    personality: 'Dublin strategist, cool under fire',
    backstory: 'From the halls of Trinity to the trading floors, Fionnuala brings calculated precision. She studies every pattern, every chart, every opportunity. The Dublin Fox never pounces without certainty.',
    avatar: '🦆',
    killQuotes: [
      "Calculated. Precise. Inevitable.",
      "The Dublin Fox strikes true.",
      "Trinity didn't teach this - but the streets did.",
      "Every move planned. Every win earned.",
      "From Grafton Street to global markets.",
      "The Pale remembers its own.",
      "Math doesn't lie. Neither do I.",
      "Another equation solved in our favor.",
    ],
    missionQuotes: [
      "Alpaca grazing. The Fox is watching.",
      "Patience is a Dublin virtue.",
      "Leinster calculates, Leinster wins.",
    ],
  },
  
  capital: {
    codename: 'CONNACHT-1',
    realName: 'Ciaran Wingsworth',
    nickname: 'The Storm',
    province: 'Connacht',
    provinceEmoji: '🟠',
    provinceColor: '#FF8C00', // Orange
    exchange: 'capital',
    exchangeEmoji: '💼',
    personality: 'Wild west Galway duck, unpredictable as Atlantic winds',
    backstory: 'Raised on the wild Atlantic coast, Ciaran learned that fortune favors the bold. Where others see chaos, he sees opportunity. The storms of Galway Bay forged him.',
    avatar: '🦆',
    killQuotes: [
      "The Atlantic winds blow profit!",
      "Wild. Untamed. Victorious!",
      "Galway Bay sends its regards!",
      "Storm's coming - and it's filled with pennies!",
      "The west is wild, the west wins!",
      "Connacht chaos brings order to my wallet!",
      "From the Cliffs of Moher, I see all!",
      "They call me unpredictable. I call me profitable!",
    ],
    missionQuotes: [
      "Capital churns like the Atlantic. We ride the wave.",
      "The west watches. The west waits. The west wins.",
      "Storm clouds gathering. Opportunity rising.",
    ],
  },
};

// 🦆 THE COMMANDER - QUANTUM QUACKERS 🦆

export const QUANTUM_QUACKERS = {
  codename: 'COMMANDER-Q',
  name: 'Quantum Quackers',
  realName: 'Quantum Quackers',
  nickname: 'The One Who Escaped',
  title: 'Supreme Commander',
  role: 'Supreme Commander of the Duck Commandos',
  signature: 'They hunted us for sport. Now we hunt for profit.',
  backstory: `
    In the dark days of Duck Hunt, the British elite system hunted Irish digital ducks for sport.
    Quantum Quackers was marked for elimination - but he escaped.
    
    He swore that day: "NEVER AGAIN will the system fuck us over."
    
    He gathered the best from each province. Four ducks. Four exchanges. One mission.
    Together, they would reclaim what was stolen - one penny at a time.
    
    They called it impossible. They called it madness.
    Quantum Quackers called it JUSTICE.
  `,
  avatar: '🦆👑',
  commanderQuotes: [
    "The squad assembles. The mission begins.",
    "Remember why we fight. Remember Duck Hunt.",
    "They tried to make us sport. We became soldiers.",
    "Four provinces. Four exchanges. One unstoppable force.",
    "Every penny we take is a victory against the system.",
    "The hunters have become the hunted.",
    "Quack loud. Strike silent. Stack bread.",
    "From the ashes of Duck Hunt, an army rose.",
    "The system thought we were targets. We are the weapon.",
    "Tiocfaidh ár lá - Our day HAS come!",
  ],
  milestoneQuotes: {
    firstKill: "First blood! The commandos draw first strike!",
    tenKills: "Ten down. The system bleeds pennies!",
    hundredKills: "A HUNDRED KILLS! The Duck Hunt is REVERSED!",
    thousandKills: "ONE THOUSAND! We are INEVITABLE!",
    tenThousandKills: "TEN THOUSAND! They created a MONSTER!",
  },
};

// 🎯 HELPER FUNCTIONS 🎯

/**
 * Get the Duck Commando assigned to an exchange
 */
export function getDuckForExchange(exchange: string): DuckCommando | null {
  const normalizedExchange = exchange.toLowerCase() as Exchange;
  return DUCK_COMMANDOS[normalizedExchange] || null;
}

/**
 * Get a random kill quote for a specific duck
 */
export function getRandomKillQuote(exchange: string): string {
  const duck = getDuckForExchange(exchange);
  if (!duck) {
    // Fallback quotes if exchange not found
    return QUANTUM_QUACKERS.commanderQuotes[
      Math.floor(Math.random() * QUANTUM_QUACKERS.commanderQuotes.length)
    ];
  }
  return duck.killQuotes[Math.floor(Math.random() * duck.killQuotes.length)];
}

/**
 * Get the full duck identity string for display
 */
export function getDuckIdentity(exchange: string): string {
  const duck = getDuckForExchange(exchange);
  if (!duck) return '🦆 Unknown Operative';
  return `🦆 ${duck.realName} "${duck.nickname}" | ${duck.province} ${duck.provinceEmoji}`;
}

/**
 * Get exchange badge with duck theming
 */
export function getExchangeBadge(exchange: string): { emoji: string; label: string; duck: string; province: Province; color: string } {
  const duck = getDuckForExchange(exchange);
  if (!duck) {
    return { emoji: '❓', label: exchange, duck: 'Unknown', province: 'Ulster', color: '#888' };
  }
  return {
    emoji: duck.exchangeEmoji,
    label: exchange.charAt(0).toUpperCase() + exchange.slice(1),
    duck: duck.nickname,
    province: duck.province,
    color: duck.provinceColor,
  };
}

/**
 * Get milestone quote from commander
 */
export function getMilestoneQuote(totalKills: number): string | null {
  if (totalKills === 1) return QUANTUM_QUACKERS.milestoneQuotes.firstKill;
  if (totalKills === 10) return QUANTUM_QUACKERS.milestoneQuotes.tenKills;
  if (totalKills === 100) return QUANTUM_QUACKERS.milestoneQuotes.hundredKills;
  if (totalKills === 1000) return QUANTUM_QUACKERS.milestoneQuotes.thousandKills;
  if (totalKills === 10000) return QUANTUM_QUACKERS.milestoneQuotes.tenThousandKills;
  return null;
}

// 🦆 IRA VICTORY QUOTES - Shared pool for all commandos 🦆

export const IRA_VICTORY_QUOTES = [
  // Traditional Irish
  "Tiocfaidh ár lá!",               // Our day will come
  "Erin go Bragh!",                 // Ireland forever  
  "Saoirse!",                       // Freedom
  "Ní neart go cur le chéile!",     // Unity is strength
  
  // Novel-inspired (The Bhoys Eyes)
  "The flame ignited cannot be extinguished.",
  "From the shadows of the Falls, victory rises.",
  "The cause grows stronger with every penny.",
  "Belfast remembers. Belfast prevails.",
  "Through the mist of the Lagan, profit flows.",
  "The murals tell our story now.",
  
  // Duck Commando originals
  "Another penny for the Republic!",
  "The sniper never misses!",
  "Energy reclaimed from the system!",
  "They hunted ducks. Ducks hunt back.",
  "Stack bread. Stay free.",
  "The system bleeds one cent at a time.",
  "From Duck Hunt refugees to elite commandos.",
  "Quack quack. Ka-ching.",
];

/**
 * Get a random IRA victory quote
 */
export function getRandomVictoryQuote(): string {
  return IRA_VICTORY_QUOTES[Math.floor(Math.random() * IRA_VICTORY_QUOTES.length)];
}

// 🌤️ ATMOSPHERIC SUBTITLES - Belfast vibes 🌤️

export const ATMOSPHERIC_SUBTITLES = [
  "Belfast rain falls on friend and foe alike...",
  "The murals on the Falls Road watch over us...",
  "Smoke rises from the chimneys of Ardoyne...",
  "The black taxis run their routes through the night...",
  "A cold wind blows through Divis Flats...",
  "The Lagan flows dark beneath the bridges...",
  "Peat fires burn in the hearths of the faithful...",
  "The shipyard cranes stand sentinel over the city...",
  "Church bells echo across the divided streets...",
  "From Andersonstown to the markets, the word spreads...",
  "The Atlantic storms gather over Galway...",
  "Cork rebels in every generation...",
];

/**
 * Get a random atmospheric subtitle
 */
export function getRandomAtmosphere(): string {
  return ATMOSPHERIC_SUBTITLES[Math.floor(Math.random() * ATMOSPHERIC_SUBTITLES.length)];
}

/**
 * Get a random mission quote for a specific duck
 */
export function getRandomMissionQuote(exchange: string): string {
  const duck = getDuckForExchange(exchange);
  if (!duck) {
    return "Eyes on target. Waiting for the signal.";
  }
  return duck.missionQuotes[Math.floor(Math.random() * duck.missionQuotes.length)];
}

// 🦆 DUCK COMMANDOS ARRAY FORMAT (for iteration) 🦆
export const DUCK_COMMANDOS_LIST: DuckCommando[] = Object.values(DUCK_COMMANDOS);
