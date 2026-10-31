import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, BookOpen, Compass, Play, Globe } from 'lucide-react';
import AdSenseUnit from '../components/AdSenseUnit';

interface ModeData {
  name: string;
  path: string;
  pool: string;
  questions: string;
  guesses: number;
  description: string;
  tips: string[];
  example: { title: string; steps: string[]; lesson: string };
  reference: {
    heading: string;
    paragraphs: string[];
    keyFacts: { label: string; detail: string }[];
  };
}

const CONTINENTAL_MODES: Record<string, ModeData> = {
  europe: {
    name: 'Europedle — Europe',
    path: '/europe',
    pool: '44 European countries (curated physical continent pool)',
    questions: '8',
    guesses: 3,
    description: 'Deduce a hidden European country using geographic subregions, coastal sea basins, shared international borders, and physical landforms. The 44-entry game pool excludes Kazakhstan, Azerbaijan, Georgia and Israel; inclusion is a game eligibility convention, not a statement about diplomatic recognition.',
    tips: [
      'Begin by isolating the European subregion (Nordic, Western, Central, Eastern, Southern/Mediterranean, or Balkan) rather than asking whether the country is in Europe.',
      'Use marginal sea access (Baltic Sea, North Sea, Mediterranean Sea, Adriatic Sea, or Black Sea) or landlocked status to partition candidates rapidly.',
      'Test shared land frontiers with major central nations such as Germany, France, or Austria to split Western from Central or Eastern European candidates.',
      'Landlocked status can distinguish inland candidates such as Austria from coastal countries such as Spain, Italy, and Norway.',
    ],
    example: {
      title: 'Kosovo: Landlocked Status and Balkan Frontiers',
      steps: [
        'Kosovo is an eligible candidate within the European game pool; eligibility does not imply universal diplomatic recognition.',
        'Asking "Is the country landlocked?" evaluates to affirmative; interior river systems draining toward the Adriatic or Black Sea do not confer maritime coastline.',
        'Querying "Does it border Albania?" also yields yes, but Montenegro and North Macedonia share that border too.',
        'A further question about Serbia still leaves North Macedonia as a possibility, so these clues alone do not establish a unique answer.',
      ],
      lesson: 'Verify multiple independent spatial clues (landlocked status plus multiple adjacent land neighbors) before expending a guess attempt.',
    },
    reference: {
      heading: 'European Regional Geography & Maritime Topography',
      paragraphs: [
        'The European continent encompasses approximately 10.18 million square kilometres, characterized by an exceptionally complex coastline indented by major marginal and semi-enclosed seas. Geographers partition the continent into six core macroregions: Northern Europe (Scandinavia, the Baltic states, and the British Isles), Western Europe (the Low Countries, France, and Monaco), Central Europe (the Alpine states and Visegrád Group), Southern and Mediterranean Europe (the Iberian, Italian, and Greek peninsulas), Southeastern Europe (the Balkan nations), and Eastern Europe (the expansive East European Plain stretching toward the Ural Mountains).',
        'European geography contrasts oceanic access with interior landlocked locations such as Austria, Switzerland and Kosovo. Coastal countries border distinctive marginal seas: the Baltic Sea in the north, the North Sea and Norwegian Sea along the Atlantic margin, the Mediterranean Sea to the south, and the Black Sea in the southeast. Counts depend on the geographic and political scope used.',
        'Major orographic barriers and river arteries structure continental connectivity. The Alps, Carpathians, Pyrenees, Apennines, and Scandinavian Mountains divide climate zones and historical frontiers. Meanwhile, transnational river corridors — most notably the Danube (which flows through or borders 10 sovereign nations from the Black Forest to the Black Sea) and the Rhine (Europe’s primary commercial fluvial axis) — provide critical geographical reference lines for deductive puzzle solvers.',
      ],
      keyFacts: [
        { label: 'Geographic Macroregions', detail: 'Northern, Western, Central, Southern, Southeastern and Eastern Europe; regional definitions can overlap' },
        { label: 'Landlocked vs. Coastal', detail: 'Austria and Switzerland are landlocked; Poland and Italy have sea coasts' },
        { label: 'Major Maritime Basins', detail: 'Baltic Sea, North Sea, Mediterranean Sea (Adriatic, Tyrrhenian, Aegean), Black Sea, Norwegian Sea' },
        { label: 'Key Mountain Dividers', detail: 'Alps (highest peak Mont Blanc 4,808 m), Carpathians, Pyrenees, Apennines, Urals' },
      ],
    },
  },
  asia: {
    name: 'Asiadle — Asia',
    path: '/asia',
    pool: '48 Asian countries (excludes Egypt and Israel)',
    questions: '8',
    guesses: 3,
    description: 'Find a hidden Asian nation across the Earth’s largest continent using regional divisions, mountain barriers, river drainage basins, and maritime interfaces. The candidate pool includes 48 countries spanning from the Levant and Arabian Peninsula to the Japanese archipelago and maritime Southeast Asia.',
    tips: [
      'Partition the continent early by querying one of the 5 UN geographic realms: West Asia/Middle East, Central Asia, South Asia, East Asia, or Southeast Asia.',
      'Distinguish true oceanic coastlines (Indian, Pacific, or Arctic Oceans) from endorheic inland lake shores like the Caspian Sea.',
      'Use island nation status to separate large archipelagic states (Indonesia, Japan, Philippines, Sri Lanka, Maldives) from mainland continental powers.',
      'Leverage major mountain frontiers (Himalayas, Tian Shan, Hindu Kush) and extensive land borders to eliminate entire regional clusters.',
    ],
    example: {
      title: 'Azerbaijan: Endorheic Coastlines vs. Open Marine Access',
      steps: [
        'Azerbaijan is an eligible candidate in the 48-nation Asian pool (excluded from Europedle as a transcontinental Caucasian nation).',
        'Although Azerbaijan features extensive coastline along the Caspian Sea, the Caspian is an endorheic inland lake without natural oceanic outlets. Therefore, "Is it landlocked?" evaluates to affirmative.',
        'Querying "Does it border the Caspian Sea?" evaluates separately to affirmative, confirming Caspian littoral status while maintaining landlocked classification.',
        'Asking "Does it border Georgia and Iran?" cleanly separates Azerbaijan from Central Asian Caspian neighbors like Turkmenistan and Kazakhstan.',
      ],
      lesson: 'Coastline on an endorheic basin like the Caspian Sea does not grant marine coastal access; Caspian littoral states remain landlocked in geographic taxonomy.',
    },
    reference: {
      heading: 'Asian Macroregions, Mountain Barriers & Endorheic Basins',
      paragraphs: [
        'Asia is Earth’s largest and most populous continent, covering roughly 44.58 million square kilometres — approximately 30% of the planet’s land area. Physical geographers divide Asia into five massive geographic realms: West Asia (the Middle East, encompassing the Anatolian plateau, Arabian Peninsula, Levant, and Iranian plateau), Central Asia (the five former Soviet steppe and mountain republics), South Asia (the Indian subcontinent bounded by the Himalayas), East Asia (the Chinese heartland, Korean Peninsula, and Japanese archipelago), and Southeast Asia (continental Indochina and the immense maritime Malay Archipelago).',
        'The continent’s hydrography is characterized by profound contrasts between vast external oceanic watersheds and massive interior endorheic basins. Peripheral rivers drain into the Arctic Ocean (Ob, Yenisey, Lena), Pacific Ocean (Amur, Yellow/Huang He, Yangtze/Chang Jiang, Mekong), and Indian Ocean (Brahmaputra, Ganges, Indus, Tigris, Euphrates). In stark contrast, Central Asia and the interior Middle East form the world’s largest endorheic drainage systems, where precipitation drains into terminal lakes like the Caspian Sea and the remnant Aral Sea, or evaporates in arid sinks without reaching the global ocean.',
        'Asia contains Earth’s most formidable orographic systems, generated by the ongoing tectonic collision between the Indian and Eurasian plates. The Himalayas contain all 14 global peaks exceeding 8,000 metres (including Mount Everest at 8,848.86 m). Coupled with the Karakoram, Hindu Kush, Pamir, and Tian Shan ranges, this "Roof of the World" forms an impassable climatic and geopolitical divide separating South and Central Asia from the northern plains.',
      ],
      keyFacts: [
        { label: 'Geographic Realms', detail: 'West Asia (18), Central Asia (5), South Asia (8), East Asia (5), Southeast Asia (11)' },
        { label: 'Landlocked States (12)', detail: 'Afghanistan, Armenia, Azerbaijan, Bhutan, Kazakhstan, Kyrgyzstan, Laos, Mongolia, Nepal, Tajikistan, Turkmenistan, Uzbekistan' },
        { label: 'Oceanic Interfaces', detail: 'Pacific Ocean (East/SE Asia), Indian Ocean (South/SE/West Asia), Arctic Ocean (North Asia)' },
        { label: 'Double Landlocked', detail: 'Uzbekistan is one of only two doubly landlocked countries worldwide (surrounded exclusively by landlocked states)' },
      ],
    },
  },
  africa: {
    name: 'Africadle — Africa',
    path: '/africa',
    pool: '54 sovereign African nations',
    questions: '8',
    guesses: 3,
    description: 'Identify a sovereign African nation from an all-inclusive 54-country continental pool using bioclimatic zones, the Great Rift Valley, oceanic and inland seas, and international land boundaries.',
    tips: [
      'Query the UN African subregions (North Africa/Maghreb, West Africa, Central/Middle Africa, East Africa, or Southern Africa) as your initial deductive filter.',
      'Take advantage of the Equator: seven African nations cross 0° latitude, allowing players to separate equatorial states from northern desert or southern plateau realms.',
      'Distinguish oceanic baselines: nations border the Atlantic Ocean (west), Indian Ocean (east), Mediterranean Sea (north), or Red Sea (northeast).',
      'Remember that Africa contains 16 landlocked countries; checking coastal access immediately bisects the candidate pool.',
    ],
    example: {
      title: 'Egypt: Dual Marine Basins and Continental Frontiers',
      steps: [
        'Egypt is an eligible nation in Africadle (excluded from Asiadle, with the Sinai Peninsula recognized as its Asian transcontinental territory).',
        'Querying "Does it border the Mediterranean Sea?" evaluates to affirmative, isolating North African coastal states from sub-Saharan nations.',
        'Asking "Does it have a coastline on the Red Sea?" also evaluates to affirmative, confirming Egypt’s unique dual-basin coastal geography.',
        'Querying "Does it border Sudan?" confirms the southern land boundary and uniquely identifies Egypt.',
      ],
      lesson: 'Dual-sea nations like Egypt, Morocco, or South Africa can be isolated rapidly by testing their distinct named maritime coastlines.',
    },
    reference: {
      heading: 'African Bioclimatic Zones, Rift Systems & Hydrography',
      paragraphs: [
        'Africa is Earth’s second-largest continent, spanning approximately 30.37 million square kilometres. Uniquely among continents, it extends almost symmetrically across both the Northern and Southern Hemispheres, bisected by the Equator. Geographers classify Africa into five primary regions: North Africa (dominated by the Sahara Desert and Mediterranean coastline), West Africa (extending from the Sahel down to the forested Gulf of Guinea), Central or Middle Africa (the vast equatorial Congo River basin), East Africa (the tectonic Horn of Africa and Great Lakes plateau), and Southern Africa (the high veld, Kalahari Desert, and Cape region).',
        'The continent’s physical structure is shaped by the East African Rift System, an active divergent tectonic plate boundary stretching over 6,000 kilometres from the Red Sea down to Mozambique. This geological trench has created Africa’s Great Lakes — including Lake Victoria (Earth’s second-largest freshwater lake by area), Lake Tanganyika (the world’s second-deepest lake at 1,470 m), and Lake Malawi — alongside dramatic volcanic massifs like Mount Kilimanjaro (5,895 m) and Mount Kenya.',
        'Africa’s hydrological network features four colossal river systems: the Nile (flowing northward over 6,650 km to the Mediterranean), the Congo (Earth’s second-largest river by discharge and the deepest recorded at over 220 m), the Niger (forming a great crescent through West Africa), and the Zambezi (plunging over Victoria Falls into the Indian Ocean). Despite these waterways, 16 African states are completely landlocked: Botswana, Burkina Faso, Burundi, Central African Republic, Chad, Eswatini, Ethiopia, Lesotho, Malawi, Mali, Niger, Rwanda, South Sudan, Uganda, Zambia, and Zimbabwe.',
      ],
      keyFacts: [
        { label: 'Subregions (54 states)', detail: 'North Africa (6), West Africa (16), Central Africa (9), East Africa (18), Southern Africa (5)' },
        { label: 'Landlocked Nations (16)', detail: 'Botswana, Burkina Faso, Burundi, CAR, Chad, Eswatini, Ethiopia, Lesotho, Malawi, Mali, Niger, Rwanda, South Sudan, Uganda, Zambia, Zimbabwe' },
        { label: 'Equator-Straddling States (7)', detail: 'Gabon, Republic of the Congo, Democratic Republic of the Congo, Uganda, Kenya, Somalia, São Tomé and Príncipe' },
        { label: 'Enclaves & Kingdoms', detail: 'Lesotho (enclaved inside South Africa), Eswatini (bordered by South Africa and Mozambique)' },
      ],
    },
  },
  americas: {
    name: 'Americadle — The Americas',
    path: '/americas',
    pool: '35 American nations (North and South America combined)',
    questions: '8',
    guesses: 3,
    description: 'Deduce a sovereign nation across the Western Hemisphere, spanning North America, Central America, the Caribbean island archipelagos, and South America in a unified 35-country pool.',
    tips: [
      'Specify North America versus South America early; an unqualified question about "America" covers both continents.',
      'Use the Central American isthmus (7 countries) or Caribbean island status (13 sovereign island states) to narrow geographic scope quickly.',
      'Check oceanic orientation: countries may border the Pacific Ocean, the Atlantic Ocean, the Caribbean Sea, or both (e.g., Mexico, Guatemala, Honduras, Nicaragua, Costa Rica, Panama, Colombia).',
      'Remember that South America has only two landlocked nations: Bolivia and Paraguay.',
    ],
    example: {
      title: 'Brazil: Continental Dominance and Trans-Equatorial Reach',
      steps: [
        'Brazil is an eligible nation in the combined 35-country Americas pool.',
        'Asking "Is it in South America?" evaluates to affirmative, cutting the pool down to 12 South American sovereign states.',
        'Asking "Does it cross the Equator?" evaluates to affirmative, as Brazil extends from the northern hemisphere (+5°N) deep into the southern hemisphere (-33°S).',
        'Querying "Does it border Argentina and Peru?" verifies Brazil’s immense border network (bordering 10 of the other 11 South American entities).',
      ],
      lesson: 'Brazil’s extensive territorial borders and trans-equatorial coordinates allow decisive elimination once South America is confirmed.',
    },
    reference: {
      heading: 'Pan-American Physical Geography, Cordilleras & Archipelagos',
      paragraphs: [
        'The Americas stretch over 14,000 kilometres from the high Arctic islands of northern Canada to Cape Horn at the southern tip of Tierra del Fuego, encompassing approximately 42.55 million square kilometres. This vast Western Hemisphere landmass is structured into four primary divisions: North America (Canada, the United States, and Mexico), Central America (the seven isthmian nations: Guatemala, Belize, El Salvador, Honduras, Nicaragua, Costa Rica, and Panama), the Caribbean (13 sovereign island nations across the Greater and Lesser Antilles and Lucayan Archipelago), and South America (12 sovereign states).',
        'A continuous, active orogenic spine dominates the western margin of both continents: the North American Cordillera (including the Rocky Mountains, Sierra Nevada, and Sierra Madre) transitions through the volcanic arc of Central America into the Andes of South America. Spanning over 7,000 kilometres along the Pacific coast with peaks exceeding 6,900 metres (Aconcagua at 6,961 m), the Andes form the longest continental mountain range on Earth, creating a sharp climatic barrier that isolates the arid Pacific coast from the lush interior plains.',
        'To the east of the cordillera lie the planet’s greatest fluvial drainage basins: the Amazon River basin (discharging roughly 20% of all global river flow into the Atlantic), the Paraná–Paraguay basin draining through the Río de la Plata, the Orinoco basin in northern South America, and the Mississippi–Missouri river basin in North America. Unlike Africa or Europe, only two sovereign nations in the Americas are landlocked: Bolivia and Paraguay, both situated in the South American interior.',
      ],
      keyFacts: [
        { label: 'Geographic Realms (35)', detail: 'North America (3), Central America (7), Caribbean Islands (13), South America (12)' },
        { label: 'Landlocked Nations (2)', detail: 'Bolivia and Paraguay (both in South America)' },
        { label: 'Dual-Ocean Access', detail: 'Canada, USA, Mexico, Guatemala, Honduras, Nicaragua, Costa Rica, Panama, Colombia' },
        { label: 'Island Archipelagos', detail: '13 sovereign island states in the Caribbean Sea and Atlantic Ocean' },
      ],
    },
  },
};

const MODES: Record<string, ModeData> = {
  countrydle: {
    name: 'Countrydle — World Countries',
    path: '/game',
    pool: '195 playable countries',
    questions: '10',
    guesses: 3,
    description: 'Deduce a hidden country from the game catalog using factual yes/no questions about continents, borders, coastlines, and physical geography. The playable catalog is a game convention, not a list of universally recognized states.',
    tips: [
      'Bisect the globe early by querying continent clusters or hemisphere coordinates relative to the Equator (0° lat) and Prime Meridian (0° long).',
      'Distinguish open marine coastlines from landlocked status: a country on an inland sea can still be landlocked.',
      'Use named international land borders to verify candidate clusters once a region is identified.',
      'Check explicit numeric metrics like population or surface area in square kilometres to differentiate large nations from microstates.',
    ],
    example: {
      title: 'Poland: Combining coastal and border clues',
      steps: [
        'For this practice example, suppose the hidden country is Poland.',
        '“Is it in Europe?” — Yes. Keep European candidates, allowing for the game’s continent conventions.',
        '“Is it landlocked?” — No. Poland has a Baltic Sea coast, so landlocked candidates can be ruled out.',
        '“Does it border Germany?” — Yes. Poland shares a land border with Germany, but other coastal countries do too.',
      ],
      lesson: 'Combine independent clues before guessing. These three answers fit Poland but do not prove it is the only candidate; a further specific question can help.',
    },
    reference: {
      heading: 'Country eligibility and physical geography',
      paragraphs: [
        'The game catalog contains 195 playable countries. Kosovo is included and Israel is excluded from playable targets and guesses. These eligibility choices do not establish universal diplomatic recognition or change physical geography. Continent associations can overlap, so pool counts need not add up to the worldwide catalog.',
        'Geographic clues can narrow a candidate list without settling it. A country can span more than one hemisphere or continent, and the game uses stored associations and specific territorial conventions rather than inferring every classification from a map.',
        'Landlocked countries lack direct access to the World Ocean or its connected seas. Liechtenstein and Uzbekistan are doubly landlocked: each is surrounded by landlocked countries. An inland sea such as the Caspian does not provide marine access.',
      ],
      keyFacts: [
        { label: 'Continent associations', detail: 'Some countries belong to more than one continental pool; game-specific exclusions also apply.' },
        { label: 'Landlocked examples', detail: 'Austria, Mongolia, Botswana and Paraguay lack marine coastlines.' },
        { label: 'Doubly Landlocked', detail: 'Liechtenstein (Europe) and Uzbekistan (Asia)' },
        { label: 'Transcontinental States', detail: 'Turkey, Russia, Egypt, Kazakhstan, Azerbaijan, Georgia, Panama' },
      ],
    },
  },
  flagdle: {
    name: 'Flagdle — Daily Flag Reveal',
    path: '/flagdle',
    pool: '195 national flags of playable countries',
    questions: 'Unlimited helper questions',
    guesses: 12,
    description: 'Identify a secret national flag as it is progressively revealed across a 12-tile grid (3 rows × 4 columns). Each guess unmasks another tile, while optional helper questions provide color and symbol clues without spending guess attempts.',
    tips: [
      'Examine the geometric layout of unmasked tiles: horizontal tricolors, vertical tricolors, Nordic crosses, and saltires provide immediate structural clues.',
      'Ask helper questions about primary heraldic tinctures (red, white, blue, yellow, green, black) to deduce colors hidden under unrevealed tiles.',
      'Check for distinct national emblems like stars, crescents, suns, eagles, or coats of arms.',
      'Identify regional color traditions: Pan-African (green-yellow-red), Pan-Arab (black-white-green-red), or Pan-Slavic (red-white-blue).',
    ],
    example: {
      title: 'Kosovo: Progressive Unmasking of Gold and Stars',
      steps: [
        'The flag of Kosovo features a dark blue field charged with a gold map silhouette of Kosovo surmounted by an arc of six white five-pointed stars.',
        'Early tile unmasking reveals only blue; asking "Does the flag contain yellow or gold?" evaluates to affirmative, narrowing the possibilities.',
        'A subsequent helper question asking "Does the flag feature stars?" evaluates to affirmative, confirming an astronomical charge.',
        'As the central gold silhouette appears, Kosovo is cleanly differentiated from Bosnia & Herzegovina or European Union layouts.',
      ],
      lesson: 'Helper questions do not cost guesses in Flagdle; use them freely to verify concealed colors before committing a country guess.',
    },
    reference: {
      heading: 'Vexillological Classifications & Heraldic Emblem Systems',
      paragraphs: [
        'Vexillology — the scholarly study of flags — classifies national banners through precise geometric layouts, color heraldry (tinctures), and cultural symbol systems. The 195 national flags of the world reflect profound historical, political, and cultural movements. The most prevalent layout is the tricolor, which originated in Europe in two primary forms: the Dutch horizontal tricolor (inspiring Russia and the Pan-Slavic flags) and the French vertical Tricolore (which influenced Italy, Ireland, Romania, Chad, Mali, and Mexico).',
        'Several distinct regional families dominate national flag design. The Nordic Cross — a cross whose vertical bar is shifted toward the hoist — unites Northern Europe (Denmark, Sweden, Norway, Finland, and Iceland). The Pan-African colors (green, yellow/gold, and red, derived from the historic Ethiopian empire) feature across dozens of sub-Saharan banners (Ghana, Senegal, Cameroon, Mali, Guinea). The Pan-Arab colors (black, white, green, and red, representing the historical Rashidun, Umayyad, Abbasid, and Fatimid caliphates) define the flags of Egypt, Jordan, Iraq, Syria, UAE, Kuwait, and Palestine. The Pan-Slavic colors (red, white, and blue) are shared by Russia, Serbia, Slovakia, the Czech Republic, Croatia, and Slovenia.',
        'Beyond simple stripes, national flags employ distinctive charges and emblems. Celestial motifs are widespread: 53 national flags incorporate stars, while crescents appear prominently across Islamic nations (Turkey, Pakistan, Algeria, Tunisia, Mauritania, Malaysia). Unique structural outliers also test player observation: Nepal possesses the world’s only non-quadrilateral sovereign flag (a double pennant), while Switzerland and Vatican City feature square flags (1:1 aspect ratio), and the United States, Malaysia, Greece, and Liberia utilize canton layouts with stripes.',
      ],
      keyFacts: [
        { label: 'Core Geometric Layouts', detail: 'Horizontal tricolors, vertical tricolors, Nordic crosses, saltires, cantons, triangles' },
        { label: 'Regional Color Traditions', detail: 'Pan-African (green/gold/red), Pan-Arab (black/white/green/red), Pan-Slavic (white/blue/red)' },
        { label: 'Non-Standard Flags', detail: 'Nepal (double-pennant), Switzerland & Vatican City (square 1:1 ratio)' },
        { label: 'Common Emblem Motifs', detail: 'Five-pointed stars, Islamic crescents, radiant suns, coats of arms, national fauna' },
      ],
    },
  },
  ...CONTINENTAL_MODES,
  'us-states': {
    name: 'US Statedle — 50 States',
    path: '/us-states',
    pool: '50 US states',
    questions: '8',
    guesses: 3,
    description: 'Find a hidden United States state using official US Census Bureau regional taxonomies, interstate land boundaries, coastal and Great Lakes water bodies, and statehood admission history.',
    tips: [
      'Begin by querying the 4 official US Census Bureau regions: Northeast, Midwest, South, or West.',
      'Distinguish marine oceanic coastlines (Atlantic, Pacific, Gulf of Mexico) from freshwater Great Lakes shorelines (Lake Superior, Michigan, Huron, Erie, Ontario).',
      'Use major river boundaries like the Mississippi River, Missouri River, Ohio River, or Columbia River to bisect candidate states.',
      'Check interstate border counts: Tennessee and Missouri share borders with 8 neighboring states, while Maine borders only 1 (New Hampshire).',
    ],
    example: {
      title: 'Florida: Peninsula Geometry and Gulf Coastline',
      steps: [
        'Florida is an eligible state in the 50-state pool (excluding Washington, D.C. and US territories).',
        'Asking "Is it in the South region?" evaluates to affirmative, reducing the candidate pool from 50 to 16 southern states.',
        'Querying "Does it border the Gulf of Mexico?" evaluates to affirmative, narrowing candidates to Texas, Louisiana, Mississippi, Alabama, and Florida.',
        'Asking "Does it also border the Atlantic Ocean?" evaluates to affirmative, uniquely confirming the Floridian peninsula.',
      ],
      lesson: 'Testing dual marine water bodies (Gulf of Mexico and direct Atlantic coastline) immediately isolates Florida from all other states.',
    },
    reference: {
      heading: 'US Regional Geography, Hydrographic Divides & Biomes',
      paragraphs: [
        'The 50 United States span 9.83 million square kilometres across North America, presenting a diverse physical geography bounded by the Atlantic Ocean, Arctic Ocean, Pacific Ocean, and Gulf of Mexico. The US Census Bureau organizes the 50 states into four primary statistical regions and nine subordinate divisions: the Northeast (New England and Middle Atlantic divisions; 9 states), the Midwest (East North Central and West North Central divisions; 12 states), the South (South Atlantic, East South Central, and West South Central divisions; 16 states), and the West (Mountain and Pacific divisions; 13 states).',
        'Hydrologically, the United States is split by the Continental Divide along the crest of the Rocky Mountains, which separates watersheds draining eastward toward the Atlantic and Gulf of Mexico from those draining westward toward the Pacific. The immense Mississippi–Missouri river system drains approximately 41% of the contiguous 48 states, serving as a historic internal boundary line between eastern and western states. Meanwhile, the five Laurentian Great Lakes (Superior, Michigan, Huron, Erie, Ontario) contain 21% of the world’s surface freshwater, creating thousands of miles of lacustrine shoreline for eight northern states (MN, WI, IL, IN, MI, OH, PA, NY).',
        'Maritime access defines 23 states bordering oceans or the Gulf of Mexico, while 27 states are landlocked (though eight border the Great Lakes). The two non-contiguous states represent geographic extremes: Alaska is the largest state by land area (1.72 million km²), extending into the Arctic and Pacific with more coastline than the rest of the US combined, while Hawaii is a remote tropical volcanic archipelago in Polynesia, over 3,800 kilometres southwest of the California coast.',
      ],
      keyFacts: [
        { label: 'Census Bureau Regions', detail: 'Northeast (9), Midwest (12), South (16), West (13)' },
        { label: 'Coastal vs. Interior', detail: '23 marine coastal states (Atlantic, Gulf, Pacific, Arctic); 27 landlocked states' },
        { label: 'Great Lakes States (8)', detail: 'Minnesota, Wisconsin, Illinois, Indiana, Michigan, Ohio, Pennsylvania, New York' },
        { label: 'Border Extremes', detail: 'Tennessee and Missouri (8 neighbors each); Maine (1 neighbor: NH); Alaska & Hawaii (0 land neighbors)' },
      ],
    },
  },
  wojewodztwa: {
    name: 'Województwodle — 16 Voivodeships',
    path: '/wojewodztwa',
    pool: '16 Polish voivodeships (Województwa)',
    questions: '5',
    guesses: 2,
    description: 'Identify one of Poland’s 16 first-tier administrative regions (województwa) within a tight budget of 5 questions and 2 guesses. Navigate historical Polish provinces, Baltic Sea maritime access, foreign borders, and major river basins.',
    tips: [
      'Test Baltic Sea maritime access early: only Pomorskie and Zachodniopomorskie have open Baltic coastlines.',
      'Check for foreign international borders: 12 voivodeships border foreign states, while 4 (Mazowieckie, Łódzkie, Wielkopolskie, Świętokrzyskie) are entirely interior.',
      'Identify the drainage basin: Poland is predominantly drained by the Wisła (54%) and Odra (34%) river systems.',
      'Query mountain relief in the south: the Sudety and Karpaty (Beskidy, Tatry) border Dolnośląskie, Śląskie, Małopolskie, and Podkarpackie.',
    ],
    example: {
      title: 'Zachodniopomorskie: Baltic Access and German Frontier',
      steps: [
        'Zachodniopomorskie is one of Poland’s 16 voivodeships, situated in the northwestern corner of the country.',
        'Asking "Does it have access to the Baltic Sea?" evaluates to affirmative, narrowing the field immediately to Pomorskie and Zachodniopomorskie.',
        'Asking "Does it border Germany?" evaluates to affirmative for Zachodniopomorskie, but not Pomorskie.',
        'This two-question sequence definitively isolates the target, leaving remaining question budget intact.',
      ],
      lesson: 'In a 5-question game, combining maritime access with an international border question can solve the puzzle in just two turns.',
    },
    reference: {
      heading: 'Regional geography, river basins and borders of Poland’s 16 voivodeships',
      paragraphs: [
        'Since the administrative reform of January 1, 1999, Poland has been divided into 16 voivodeships, the first tier of local government and state administration. Its terrain runs in bands from the southern Baltic coastal lowlands through the Pomeranian, Masurian and Wielkopolska lake districts and central lowlands to the southern uplands, Sudetes and Carpathians.',
        'Most of Poland drains into the Baltic Sea. The Wisła is its longest river at 1,047 km and its basin drains 54% of the country; the Odra basin drains 34%. Pomorskie and Zachodniopomorskie directly reach the open Baltic Sea. Warmińsko-Mazurskie borders the Vistula Lagoon, which the Vistula Spit separates from the open sea.',
        'Poland borders seven countries: Germany, Czechia, Slovakia, Ukraine, Belarus, Lithuania and Russia’s Kaliningrad Oblast. Twelve voivodeships have an international border; Mazowieckie, Łódzkie, Wielkopolskie and Świętokrzyskie are inland.',
      ],
      keyFacts: [
        { label: 'Regional division (16)', detail: 'Mazowieckie is the largest (35,500 km²); Opolskie is the smallest (9,400 km²).' },
        { label: 'Baltic access', detail: 'Pomorskie and Zachodniopomorskie reach the open sea; Warmińsko-Mazurskie borders the Vistula Lagoon.' },
        { label: 'International borders', detail: '12 border voivodeships and four inland voivodeships.' },
        { label: 'Mountain ranges', detail: 'The Carpathians include the Tatras and Beskids; the Sudetes include the Karkonosze.' },
      ],
    },
  },
  powiaty: {
    name: 'Powiatdle — 380 Counties',
    path: '/powiaty',
    pool: '380 Polish counties (314 ziemskie + 66 grodzkie)',
    questions: '15',
    guesses: 3,
    description: 'The ultimate Polish geography challenge. Deduce one of Poland’s 380 second-tier administrative units (powiaty) using parent voivodeships, city-county status, vehicle registration codes, highway transit corridors, and river networks.',
    tips: [
      'Isolate the parent voivodeship immediately: this single step narrows the search space from 380 down to an average of 24 candidates.',
      'Determine administrative status: ask whether the target is a city with county rights (miasto na prawach powiatu, 66 units) or a land county (powiat ziemski, 314 units).',
      'Use vehicle registration prefixes (tablice rejestracyjne): cities with county rights typically have 2-letter codes (e.g., KR, DW, PO), while land counties have 3-letter codes (e.g., KRA, DWR, PZ).',
      'Leverage major transport spines (Autostrada A1, A2, A4; Drogi Ekspresowe S3, S7, S8) and river courses (Wisła, Odra, Warta, Bug).',
    ],
    example: {
      title: 'Kraków vs. Powiat Krakowski: Administrative Distinction',
      steps: [
        'In Polish administrative law, the municipality of Kraków (miasto na prawach powiatu) and the surrounding powiat krakowski (powiat ziemski) are two legally distinct entities with separate borders.',
        'Asking "Is it in Małopolskie voivodeship?" evaluates to affirmative, cutting the pool from 380 to 22 Małopolska counties.',
        'Asking "Is it a city with county rights?" evaluates to affirmative for Kraków, but negative for powiat krakowski. Małopolska has three city counties: Kraków, Tarnów and Nowy Sącz.',
        'Checking the vehicle registration code prefix (KR for Kraków vs. KRA for powiat krakowski) guarantees a precise, unambiguous guess.',
      ],
      lesson: 'Never confuse a statutory city with its surrounding land county; their administrative status and vehicle plate codes are completely different.',
    },
    reference: {
      heading: 'Administrative structure, city counties and settlement in Poland',
      paragraphs: [
        'Poland’s second administrative tier comprises 380 counties: 314 land counties, each comprising several municipalities and governed by a county council and executive, and 66 cities with county rights. These cities perform both municipal and county functions.',
        'County distribution varies across the 16 voivodeships. Mazowieckie has 42 counties, including Warszawa, Radom, Płock, Siedlce and Ostrołęka as cities with county rights. Śląskie has 36 counties, including 19 cities with county rights; Opolskie has 12 counties and Lubuskie has 14.',
        'Vehicle registration prefixes help identify counties. The first letter identifies the voivodeship: W for Mazowieckie, K for Małopolskie, D for Dolnośląskie, P for Wielkopolskie, G for Pomorskie and S for Śląskie. Examples include KR for Kraków, DW for Wrocław, PO for Poznań and KRA for the surrounding Kraków land county. Major roads and the Wisła and Odra river systems provide further clues.',
      ],
      keyFacts: [
        { label: 'Legal structure (380)', detail: '314 land counties and 66 cities with county rights.' },
        { label: 'Urban concentration', detail: 'Śląskie has 19 cities with county rights.' },
        { label: 'Registration plates', detail: 'Prefixes identify the voivodeship and local registration area; examples include KR, DW, KRA and DWR.' },
        { label: 'Area extremes', detail: 'Powiat białostocki is the largest (2,985 km²); Świętochłowice is the smallest city county (13.3 km²).' },
      ],
    },
  },
};

export default function ModeGuidePage() {
  const { modeId } = useParams<{ modeId: string }>();
  const normalizedId = modeId === 'us_statedle' ? 'us-states' : modeId;
  const mode = normalizedId ? MODES[normalizedId] : undefined;

  if (!mode) {
    return (
      <div className="mx-auto max-w-4xl space-y-5 py-8">
        <h1 className="font-serif text-4xl text-sand-100">Mode guide not found</h1>
        <p className="text-base leading-7 text-zinc-400">This address does not match an available daily-mode guide.</p>
        <Link to="/explore" className="text-emerald-300 underline underline-offset-4">Return to Geography Explorer</Link>
      </div>
    );
  }

  const isCountryMode = normalizedId === 'countrydle' || normalizedId === 'flagdle' || (normalizedId !== undefined && normalizedId in CONTINENTAL_MODES);

  return (
    <div className="mx-auto max-w-4xl space-y-8 py-5 text-zinc-300 md:space-y-10 md:py-10">
      <Link to="/explore" className="inline-flex items-center gap-2 text-sm text-emerald-300 underline underline-offset-4">
        <ArrowLeft size={16} aria-hidden="true" />
        Back to Geography Explorer
      </Link>
      
      <header className="border-b border-white/10 pb-8">
        <p className="mb-4 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
          <BookOpen size={14} aria-hidden="true" />
          Mode deduction guide
        </p>
        <h1 className="font-serif text-4xl leading-tight text-sand-100 sm:text-5xl">{mode.name}</h1>
        <p className="mt-4 text-base leading-7">{mode.description}</p>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4">
            <dt className="text-zinc-400">Candidate pool</dt>
            <dd className="mt-2 text-sand-100">{mode.pool}</dd>
          </div>
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4">
            <dt className="text-zinc-400">Questions</dt>
            <dd className="mt-2 text-emerald-300">{mode.questions}</dd>
          </div>
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4">
            <dt className="text-zinc-400">Guesses</dt>
            <dd className="mt-2 text-sand-100">{mode.guesses}</dd>
          </div>
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4">
            <dt className="text-zinc-400">Daily reset</dt>
            <dd className="mt-2 text-sand-100">00:00 UTC</dd>
          </div>
        </dl>
      </header>

      <nav aria-label="Daily mode guides" className="flex flex-wrap gap-x-5 gap-y-3 text-sm">
        {Object.entries(MODES).map(([id, item]) => (
          <Link
            key={id}
            to={`/explore/modes/${id}`}
            aria-current={id === normalizedId ? 'page' : undefined}
            className="text-emerald-300 underline underline-offset-4"
          >
            {item.name.split(' — ')[0]}
          </Link>
        ))}
      </nav>

      {/* Strategy Section */}
      <section aria-labelledby="mode-strategy" className="space-y-4">
        <h2 id="mode-strategy" className="flex items-center gap-2 font-serif text-2xl text-sand-100">
          <Compass size={22} aria-hidden="true" />
          Questions that make useful distinctions
        </h2>
        <p className="text-base leading-7">
          Choose a question for the candidates you actually have left. A balanced yes/no split can be useful, but neither answer is guaranteed to eliminate half the pool; overlapping categories and missing facts matter. Prefer explicit predicates to vague terms such as nearby or large.
        </p>
        <ol className="list-decimal space-y-4 pl-6 marker:text-emerald-400">
          {mode.tips.map((tip) => (
            <li key={tip} className="pl-2 text-base leading-7">{tip}</li>
          ))}
        </ol>
      </section>

      {/* Worked Example */}
      <section aria-labelledby="mode-example" className="space-y-4 rounded-sm border border-white/10 bg-obsidian-900 p-5 sm:p-6">
        <h2 id="mode-example" className="font-serif text-2xl text-sand-100">Worked example: {mode.example.title}</h2>
        <p className="text-sm leading-6 text-zinc-400">Illustrative examples explain current fact and eligibility logic. They are not today’s hidden target, measured player results or recorded provider responses.</p>
        <ol className="list-decimal space-y-3 pl-6 marker:text-emerald-400">
          {mode.example.steps.map((step) => (
            <li key={step} className="pl-2 text-base leading-7">{step}</li>
          ))}
        </ol>
        <p className="border-t border-white/10 pt-4 text-base leading-7">{mode.example.lesson}</p>
        {normalizedId === 'countrydle' && (
          <p className="text-sm text-zinc-400">
            Geography source: <a href="https://www.britannica.com/place/Poland" className="text-emerald-300 underline underline-offset-4">Encyclopaedia Britannica, Poland</a>.
          </p>
        )}
      </section>

      {/* Mode-Specific Geographic Reference & Regional Breakdown */}
      <section aria-labelledby="mode-reference" className="space-y-5 border-t border-white/10 pt-8">
        <h2 id="mode-reference" className="flex items-center gap-2 font-serif text-2xl text-sand-100">
          <Globe size={22} aria-hidden="true" />
          {mode.reference.heading}
        </h2>
        <div className="space-y-4">
          {mode.reference.paragraphs.map((paragraph, idx) => (
            <p key={idx} className="text-base leading-7">{paragraph}</p>
          ))}
        </div>
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {mode.reference.keyFacts.map((fact, idx) => (
            <div key={idx} className="rounded-sm border border-white/10 bg-obsidian-900 p-4">
              <span className="font-mono text-xs uppercase tracking-wider text-emerald-400 block font-semibold">{fact.label}</span>
              <span className="text-sm text-sand-100 block mt-1">{fact.detail}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Conventions for Country Modes */}
      {isCountryMode && (
        <section aria-labelledby="country-conventions" className="space-y-5 border-t border-white/10 pt-8">
          <h2 id="country-conventions" className="font-serif text-2xl text-sand-100">Catalog, continent and disputed-region conventions</h2>
          <p className="text-base leading-7">
            The current worldwide pool has 195 playable countries. Kosovo is included; Israel is excluded from playable targets and guesses without removing its canonical geography or historical facts. This is a game eligibility policy, not a diplomatic recognition rule. Use the current game suggestions as the candidate list; dependencies and disputed regions shown on a map are not automatically separate guesses.
          </p>
          <p className="text-base leading-7">
            Continental candidates come from stored physical-continent associations and per-mode exclusions. Europedle additionally excludes Azerbaijan, Kazakhstan and Georgia; Asiadle additionally excludes Egypt. Americadle combines North America and South America. A country can have multiple associations, so membership in a continental pool is not proof that all of its territory lies there.
          </p>
          <p className="text-base leading-7">
            In accordance with standard geopolitical mapping conventions, Western Sahara is associated with Morocco, Gibraltar with the United Kingdom, and French Guiana with France. These simplified conventions can differ from a map’s boundary labels or a geopolitical source. They do not settle sovereignty disputes or automatically change continental eligibility.
          </p>
          <p className="text-base leading-7">
            Hemisphere associations describe stored territorial bounds, with some mainland overrides. France, for example, has both Eastern and Western associations. Island status is a sourced classification rather than simply an absence of land borders: countries sharing an island can border each other, while Australia is treated as a continent.
          </p>
          <p className="text-base leading-7">
            Country water access can include inland seas, but landlocked status uses marine access and excludes the Caspian, Aral and Dead Seas. Named direct coastlines are distinct from access through connected seas; only configured parent-water relationships are expanded, not every connection in the world’s oceans. River drainage is not coastal access.
          </p>
        </section>
      )}

      {/* Budgets & Scoring */}
      <section aria-labelledby="mode-scoring" className="space-y-4 border-t border-white/10 pt-8">
        <h2 id="mode-scoring" className="font-serif text-2xl text-sand-100">Budgets and scoring</h2>
        <p className="text-base leading-7">
          {normalizedId === 'flagdle'
            ? 'Flagdle uses 12 guesses with unlimited optional helper questions. Its win score combines +500 base points, a guess bonus from +1,500 on the first guess to +50 on the twelfth, up to +300 speed points over 3 minutes, and up to +500 streak points. It has no question-efficiency bonus.'
            : 'Question-based daily wins use +500 base points, up to +1,500 for question efficiency, up to +500 for guess efficiency, up to +300 for speed over 5 minutes, and +50 per consecutive day solved in that mode up to +500. US Statedle adds +200 and Powiatdle adds +500. Guest scores are previews; saved account results determine streak bonuses. Running out of questions does not end the game while guesses remain.'}
        </p>
        <p className="text-base leading-7">
          Friend duels are separate from these nine daily modes. Players answer each other’s questions; there is no total question or guess cap, but each action takes a turn, timers apply, and the final reply after a starting-player solve permits a guess or pass, not another question.
        </p>
      </section>

      {/* Sources & Editorial Limits */}
      <section aria-labelledby="mode-sources" className="space-y-4 border-t border-white/10 pt-8">
        <h2 id="mode-sources" className="font-serif text-2xl text-sand-100">Sources, limits and corrections</h2>
        <p className="text-base leading-7">
          {isCountryMode
            ? 'Country facts combine REST Countries, CIA World Factbook profiles distributed through factbook.json, and curated additions. Some facts are extracted from Wikipedia text using AI.'
            : 'Regional facts use local article text and infoboxes, geographic classification tables, static lists and manual corrections. They are not exclusively direct official-statistics feeds.'}{' '}
          Map boundary assets and Natural Earth-derived globe data are separate from the answer tables.
        </p>
        <p className="text-base leading-7">
          Supported templates and local facts reduce dependence on AI-generated answers, but data and interpretation can be wrong or outdated. Questions outside local coverage may use retrieved article text or general knowledge through AI fallback. An explanation is not proof of human verification.
        </p>
        <p className="text-base leading-7">
          Read the <Link to="/about" className="text-emerald-300 underline underline-offset-4">source inventory</Link>, <Link to="/how-it-works" className="text-emerald-300 underline underline-offset-4">answer-engine explanation</Link> and <Link to="/faq" className="text-emerald-300 underline underline-offset-4">FAQ</Link>. To request a correction, <Link to="/contact" className="text-emerald-300 underline underline-offset-4">contact us</Link> with the mode, date, exact question, answer, explanation and supporting source. Avoid posting today’s target publicly.
        </p>
      </section>

      <Link
        to={mode.path}
        className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-emerald-400 px-5 py-3 font-semibold text-obsidian-950 hover:bg-emerald-300"
      >
        <Play size={16} aria-hidden="true" />
        Play {mode.name.split(' — ')[0]}
      </Link>
      
      <AdSenseUnit slot="mode-guide-footer" className="mx-auto max-w-2xl pt-6" />
    </div>
  );
}
