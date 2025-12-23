"""
Dual governance category system for Nigerian presidential content analysis.
Defines separate categories for Issues (negative) and Positive Coverage (positive).
"""

# NIGERIAN FEDERAL MINISTRY-BASED CATEGORIES (36 Ministries)
# Level 1: Federal Ministries (36 categories aligned with Nigerian government structure)
FEDERAL_MINISTRIES = {
    "agriculture_food_security": "Agriculture & Food Security",
    "aviation_aerospace": "Aviation & Aerospace Development",
    "budget_economic_planning": "Budget & Economic Planning",
    "communications_digital": "Communications & Digital Economy",
    "defence": "Defence",
    "education": "Education",
    "environment_ecological": "Environment & Ecological Management",
    "finance": "Finance",
    "foreign_affairs": "Foreign Affairs",
    "health_social_welfare": "Health & Social Welfare",
    "housing_urban": "Housing & Urban Development",
    "humanitarian_poverty": "Humanitarian Affairs & Poverty Alleviation",
    "industry_trade": "Industry, Trade & Investment",
    "interior": "Interior",
    "justice": "Justice",
    "labour_employment": "Labour & Employment",
    "marine_blue_economy": "Marine & Blue Economy",
    "niger_delta": "Niger Delta Development",
    "petroleum_resources": "Petroleum Resources",
    "power": "Power",
    "science_technology": "Science & Technology",
    "solid_minerals": "Solid Minerals Development",
    "sports_development": "Sports Development",
    "tourism": "Tourism",
    "transportation": "Transportation",
    "water_resources": "Water Resources & Sanitation",
    "women_affairs": "Women Affairs",
    "works": "Works",
    "youth_development": "Youth Development",
    "livestock_development": "Livestock Development",
    "information_culture": "Information & Culture",
    "police_affairs": "Police Affairs",
    "steel_development": "Steel Development",
    "special_duties": "Special Duties & Inter-Governmental Affairs",
    "fct_administration": "Federal Capital Territory Administration",
    "art_culture_creative": "Art, Culture & Creative Economy"
}

# Level 2: Subcategories within each ministry (3-5 subcategories per ministry)
MINISTRY_SUBCATEGORIES = {
    # Agriculture & Food Security
    "agriculture_food_security": {
        "crop_production": "Crop Production",
        "livestock_management": "Livestock Management",
        "fisheries": "Fisheries",
        "rural_development": "Rural Development",
        "food_security": "Food Security"
    },
    
    # Aviation & Aerospace Development
    "aviation_aerospace": {
        "air_transport": "Air Transport Regulation",
        "aviation_safety": "Aviation Safety",
        "aerospace_research": "Aerospace Research",
        "airport_infrastructure": "Airport Infrastructure"
    },
    
    # Budget & Economic Planning
    "budget_economic_planning": {
        "national_budgeting": "National Budgeting",
        "economic_policy": "Economic Policy Formulation",
        "development_planning": "Development Planning",
        "fiscal_management": "Fiscal Management"
    },
    
    # Communications & Digital Economy
    "communications_digital": {
        "telecommunications": "Telecommunications",
        "digital_infrastructure": "Digital Infrastructure",
        "innovation_promotion": "Innovation Promotion",
        "cybersecurity": "Cybersecurity"
    },
    
    # Defence
    "defence": {
        "military_operations": "Military Operations",
        "national_security": "National Security",
        "defence_policy": "Defence Policy",
        "veteran_affairs": "Veteran Affairs"
    },
    
    # Education
    "education": {
        "primary_education": "Primary Education",
        "secondary_education": "Secondary Education",
        "higher_education": "Higher Education",
        "vocational_training": "Vocational Training",
        "educational_policy": "Educational Policy"
    },
    
    # Environment & Ecological Management
    "environment_ecological": {
        "environmental_protection": "Environmental Protection",
        "climate_change": "Climate Change Mitigation",
        "natural_resources": "Natural Resource Management",
        "waste_management": "Waste Management"
    },
    
    # Finance
    "finance": {
        "fiscal_policy": "Fiscal Policy",
        "revenue_collection": "Revenue Collection",
        "financial_regulations": "Financial Regulations",
        "debt_management": "Debt Management"
    },
    
    # Foreign Affairs
    "foreign_affairs": {
        "diplomatic_relations": "Diplomatic Relations",
        "international_cooperation": "International Cooperation",
        "consular_services": "Consular Services",
        "foreign_policy": "Foreign Policy"
    },
    
    # Health & Social Welfare
    "health_social_welfare": {
        "public_health": "Public Health",
        "healthcare_services": "Healthcare Services",
        "social_welfare": "Social Welfare Programs",
        "disease_control": "Disease Control"
    },
    
    # Housing & Urban Development
    "housing_urban": {
        "affordable_housing": "Affordable Housing",
        "urban_planning": "Urban Planning",
        "slum_upgrading": "Slum Upgrading",
        "housing_policy": "Housing Policy"
    },
    
    # Humanitarian Affairs & Poverty Alleviation
    "humanitarian_poverty": {
        "disaster_response": "Disaster Response",
        "poverty_reduction": "Poverty Reduction Programs",
        "social_interventions": "Social Interventions",
        "refugee_support": "Refugee Support"
    },
    
    # Industry, Trade & Investment
    "industry_trade": {
        "industrial_development": "Industrial Development",
        "trade_promotion": "Trade Promotion",
        "investment_facilitation": "Investment Facilitation",
        "consumer_protection": "Consumer Protection"
    },
    
    # Interior
    "interior": {
        "internal_security": "Internal Security",
        "immigration_services": "Immigration Services",
        "civil_defence": "Civil Defence",
        "border_management": "Border Management"
    },
    
    # Justice
    "justice": {
        "legal_affairs": "Legal Affairs",
        "judicial_administration": "Judicial Administration",
        "human_rights": "Human Rights Protection",
        "legal_reforms": "Legal Reforms"
    },
    
    # Labour & Employment
    "labour_employment": {
        "employment_services": "Employment Services",
        "labour_relations": "Labour Relations",
        "workplace_safety": "Workplace Safety",
        "skill_development": "Skill Development"
    },
    
    # Marine & Blue Economy
    "marine_blue_economy": {
        "maritime_transport": "Maritime Transport",
        "ocean_resources": "Ocean Resources Management",
        "coastal_development": "Coastal Development",
        "marine_policy": "Marine Policy"
    },
    
    # Niger Delta Development
    "niger_delta": {
        "regional_development": "Regional Development",
        "environmental_remediation": "Environmental Remediation",
        "community_empowerment": "Community Empowerment",
        "infrastructure_development": "Infrastructure Development"
    },
    
    # Petroleum Resources
    "petroleum_resources": {
        "oil_gas_exploration": "Oil & Gas Exploration",
        "petroleum_policy": "Petroleum Policy",
        "energy_security": "Energy Security",
        "downstream_operations": "Downstream Operations"
    },
    
    # Power
    "power": {
        "electricity_generation": "Electricity Generation",
        "transmission_distribution": "Transmission & Distribution",
        "renewable_energy": "Renewable Energy",
        "energy_policy": "Energy Policy"
    },
    
    # Science & Technology
    "science_technology": {
        "scientific_research": "Scientific Research",
        "technological_development": "Technological Development",
        "innovation_support": "Innovation Support",
        "space_exploration": "Space Exploration"
    },
    
    # Solid Minerals Development
    "solid_minerals": {
        "mining_regulation": "Mining Regulation",
        "mineral_exploration": "Mineral Exploration",
        "resource_management": "Resource Management",
        "mining_policy": "Mining Policy"
    },
    
    # Sports Development
    "sports_development": {
        "athlete_development": "Athlete Development",
        "sports_infrastructure": "Sports Infrastructure",
        "national_sports_policy": "National Sports Policy",
        "youth_sports": "Youth Sports"
    },
    
    # Tourism
    "tourism": {
        "tourism_promotion": "Tourism Promotion",
        "cultural_heritage": "Cultural Heritage Sites",
        "hospitality_industry": "Hospitality Industry",
        "tourism_policy": "Tourism Policy"
    },
    
    # Transportation
    "transportation": {
        "road_transport": "Road Transport",
        "rail_transport": "Rail Transport",
        "maritime_transport": "Maritime Transport",
        "transport_policy": "Transport Policy"
    },
    
    # Water Resources & Sanitation
    "water_resources": {
        "water_supply": "Water Supply",
        "sanitation_services": "Sanitation Services",
        "irrigation_development": "Irrigation Development",
        "water_policy": "Water Policy"
    },
    
    # Women Affairs
    "women_affairs": {
        "gender_equality": "Gender Equality",
        "women_empowerment": "Women's Empowerment",
        "child_welfare": "Child Welfare",
        "gender_policy": "Gender Policy"
    },
    
    # Works
    "works": {
        "infrastructure_development": "Infrastructure Development",
        "road_construction": "Road Construction",
        "public_works": "Public Works",
        "construction_policy": "Construction Policy"
    },
    
    # Youth Development
    "youth_development": {
        "youth_empowerment": "Youth Empowerment",
        "skill_acquisition": "Skill Acquisition",
        "youth_policy": "Youth Policy",
        "entrepreneurship": "Entrepreneurship"
    },
    
    # Livestock Development
    "livestock_development": {
        "animal_husbandry": "Animal Husbandry",
        "veterinary_services": "Veterinary Services",
        "livestock_policy": "Livestock Policy",
        "livestock_production": "Livestock Production"
    },
    
    # Information & Culture
    "information_culture": {
        "public_information": "Public Information Dissemination",
        "national_orientation": "National Orientation Programs",
        "media_relations": "Media Relations",
        "cultural_promotion": "Cultural Promotion"
    },
    
    # Police Affairs
    "police_affairs": {
        "law_enforcement": "Law Enforcement",
        "public_safety": "Public Safety",
        "police_training": "Police Training",
        "police_reforms": "Police Reforms"
    },
    
    # Steel Development
    "steel_development": {
        "steel_industry": "Steel Industry Promotion",
        "industrialization": "Industrialization",
        "resource_utilization": "Resource Utilization",
        "steel_policy": "Steel Policy"
    },
    
    # Special Duties & Inter-Governmental Affairs
    "special_duties": {
        "inter_governmental": "Inter-Governmental Coordination",
        "special_projects": "Special Projects",
        "policy_implementation": "Policy Implementation",
        "coordination": "Coordination"
    },
    
    # Federal Capital Territory Administration
    "fct_administration": {
        "urban_planning": "Urban Planning",
        "infrastructure_development": "Infrastructure Development",
        "municipal_services": "Municipal Services",
        "fct_policy": "FCT Policy"
    },
    
    # Art, Culture & Creative Economy
    "art_culture_creative": {
        "cultural_heritage": "Cultural Heritage",
        "creative_industries": "Creative Industries",
        "tourism_promotion": "Tourism Promotion",
        "cultural_policy": "Cultural Policy"
    }
}

# ISSUES CATEGORIES (Problem-focused, mapped to federal ministries)
ISSUES_CATEGORIES = {
    "economic_crisis": "Budget & Economic Planning",
    "infrastructure_failures": "Works",
    "education_problems": "Education",
    "healthcare_issues": "Health & Social Welfare",
    "security_threats": "Interior",
    "corruption_scandals": "Justice",
    "agricultural_crisis": "Agriculture & Food Security",
    "energy_shortages": "Power",
    "transportation_problems": "Transportation",
    "housing_crisis": "Housing & Urban Development",
    "environmental_issues": "Environment & Ecological Management",
    "foreign_relations_problems": "Foreign Affairs",
    "defense_weaknesses": "Defence",
    "justice_system_issues": "Justice",
    "social_welfare_failures": "Health & Social Welfare",
    "youth_unemployment": "Youth Development",
    "technology_gaps": "Science & Technology",
    "electoral_problems": "Special Duties & Inter-Governmental Affairs",
    "media_censorship": "Information & Culture",
    "regional_disparities": "Niger Delta Development",
    "disaster_response_failures": "Humanitarian Affairs & Poverty Alleviation",
    "trade_problems": "Industry, Trade & Investment",
    "employment_crisis": "Labour & Employment",
    "gender_inequality": "Women Affairs",
    "religious_tensions": "Interior",
    "oil_sector_issues": "Petroleum Resources",
    "banking_problems": "Finance",
    "administrative_inefficiency": "Special Duties & Inter-Governmental Affairs",
    "transparency_issues": "Justice",
    "crisis_management_failures": "Humanitarian Affairs & Poverty Alleviation"
}

# POSITIVE COVERAGE CATEGORIES (Achievement-focused, mapped to federal ministries)
POSITIVE_CATEGORIES = {
    "economic_achievements": "Budget & Economic Planning",
    "infrastructure_success": "Works",
    "education_progress": "Education",
    "healthcare_improvements": "Health & Social Welfare",
    "security_success": "Interior",
    "anti_corruption_success": "Justice",
    "agricultural_development": "Agriculture & Food Security",
    "energy_solutions": "Power",
    "transportation_advances": "Transportation",
    "housing_success": "Housing & Urban Development",
    "environmental_protection": "Environment & Ecological Management",
    "diplomatic_success": "Foreign Affairs",
    "defense_strengthening": "Defence",
    "justice_reforms": "Justice",
    "social_welfare_programs": "Health & Social Welfare",
    "youth_empowerment": "Youth Development",
    "technology_innovation": "Science & Technology",
    "democratic_progress": "Special Duties & Inter-Governmental Affairs",
    "media_freedom": "Information & Culture",
    "regional_development": "Niger Delta Development",
    "disaster_preparedness": "Humanitarian Affairs & Poverty Alleviation",
    "trade_success": "Industry, Trade & Investment",
    "job_creation": "Labour & Employment",
    "gender_equality": "Women Affairs",
    "religious_harmony": "Interior",
    "oil_sector_success": "Petroleum Resources",
    "banking_reforms": "Finance",
    "administrative_excellence": "Special Duties & Inter-Governmental Affairs",
    "transparency_success": "Justice",
    "crisis_management_success": "Humanitarian Affairs & Poverty Alleviation"
}

# Combined categories for backward compatibility
GOVERNANCE_CATEGORIES = {**ISSUES_CATEGORIES, **POSITIVE_CATEGORIES}

# All federal ministries for embedding-based matching
ALL_FEDERAL_MINISTRIES = FEDERAL_MINISTRIES

# Issues Category Descriptions (Problem-focused)
ISSUES_DESCRIPTIONS = {
    "economic_crisis": "Economic problems, recession, inflation, budget deficits, financial instability, economic downturn",
    "infrastructure_failures": "Failed infrastructure projects, poor roads, broken bridges, inadequate facilities, construction problems",
    "education_problems": "Educational failures, poor schools, teacher strikes, student protests, educational decline",
    "healthcare_issues": "Healthcare problems, hospital failures, medical shortages, health crises, inadequate medical care",
    "security_threats": "Security breaches, terrorist attacks, crime waves, insecurity, law enforcement failures",
    "corruption_scandals": "Corruption cases, embezzlement, bribery, fraud, abuse of power, corrupt practices",
    "agricultural_crisis": "Agricultural problems, crop failures, food shortages, farming issues, agricultural decline",
    "energy_shortages": "Power outages, energy crises, electricity problems, energy shortages, blackouts",
    "transportation_problems": "Transport failures, traffic issues, transport breakdowns, mobility problems, transport crises",
    "housing_crisis": "Housing problems, homelessness, housing shortages, poor housing conditions, housing failures",
    "environmental_issues": "Environmental problems, pollution, climate issues, environmental degradation, ecological damage",
    "foreign_relations_problems": "Diplomatic failures, international tensions, foreign policy issues, diplomatic crises",
    "defense_weaknesses": "Defense problems, military failures, security vulnerabilities, defense inadequacies",
    "justice_system_issues": "Justice system problems, court delays, legal failures, judicial corruption, justice delays",
    "social_welfare_failures": "Social welfare problems, poverty issues, welfare failures, social support breakdowns",
    "youth_unemployment": "Youth joblessness, unemployment crises, job shortages, youth employment problems",
    "technology_gaps": "Technology failures, digital divide, IT problems, technological inadequacies, tech gaps",
    "electoral_problems": "Election issues, voting problems, electoral fraud, democratic failures, election disputes",
    "media_censorship": "Media restrictions, press censorship, media suppression, information control, media freedom violations",
    "regional_disparities": "Regional inequalities, development gaps, regional conflicts, uneven development",
    "disaster_response_failures": "Disaster response problems, emergency failures, crisis management issues, relief failures",
    "trade_problems": "Trade issues, commercial failures, business problems, trade disputes, economic trade issues",
    "employment_crisis": "Job crises, employment problems, workforce issues, labor problems, job market failures",
    "gender_inequality": "Gender discrimination, women's rights violations, gender bias, inequality issues",
    "religious_tensions": "Religious conflicts, religious discrimination, interfaith tensions, religious violence",
    "oil_sector_issues": "Oil industry problems, petroleum sector issues, oil production failures, energy sector problems",
    "banking_problems": "Banking failures, financial sector issues, banking crises, financial system problems",
    "administrative_inefficiency": "Government inefficiency, bureaucratic failures, administrative problems, governance failures",
    "transparency_issues": "Lack of transparency, secrecy issues, accountability problems, information withholding",
    "crisis_management_failures": "Crisis response failures, emergency management problems, disaster response inadequacies"
}

# Positive Coverage Category Descriptions (Achievement-focused)
POSITIVE_DESCRIPTIONS = {
    "economic_achievements": "Economic success, growth, prosperity, financial stability, economic progress, development",
    "infrastructure_success": "Infrastructure achievements, successful projects, improved facilities, construction success",
    "education_progress": "Educational improvements, academic success, educational reforms, learning achievements",
    "healthcare_improvements": "Healthcare success, medical achievements, health improvements, healthcare progress",
    "security_success": "Security achievements, crime reduction, peace restoration, security improvements, safety success",
    "anti_corruption_success": "Anti-corruption achievements, integrity measures, accountability success, corruption prevention",
    "agricultural_development": "Agricultural success, farming improvements, food security achievements, agricultural progress",
    "energy_solutions": "Energy achievements, power improvements, energy success, renewable energy progress",
    "transportation_advances": "Transport improvements, mobility solutions, transportation success, transport development",
    "housing_success": "Housing achievements, housing improvements, housing development, housing progress",
    "environmental_protection": "Environmental success, conservation achievements, environmental improvements, green initiatives",
    "diplomatic_success": "Diplomatic achievements, foreign relations success, international cooperation, diplomatic progress",
    "defense_strengthening": "Defense improvements, military success, security strengthening, defense achievements",
    "justice_reforms": "Justice system improvements, legal reforms, judicial progress, justice achievements",
    "social_welfare_programs": "Social welfare success, poverty reduction, social support achievements, welfare improvements",
    "youth_empowerment": "Youth success, youth development, youth achievements, youth empowerment programs",
    "technology_innovation": "Technology success, digital progress, innovation achievements, tech improvements",
    "democratic_progress": "Democratic achievements, political progress, democratic reforms, democratic success",
    "media_freedom": "Media freedom achievements, press freedom success, information access, media progress",
    "regional_development": "Regional success, regional progress, development achievements, regional improvements",
    "disaster_preparedness": "Disaster preparedness success, emergency readiness, crisis preparedness achievements",
    "trade_success": "Trade achievements, commercial success, business growth, trade improvements",
    "job_creation": "Employment success, job creation achievements, workforce development, employment progress",
    "project_equality": "Gender equality achievements, women's rights progress, equality success, gender progress",
    "religious_harmony": "Religious harmony, interfaith cooperation, religious tolerance, religious unity",
    "oil_sector_success": "Oil industry success, petroleum achievements, energy sector progress, oil sector improvements",
    "banking_reforms": "Banking improvements, financial sector success, banking achievements, financial progress",
    "administrative_excellence": "Administrative success, government efficiency, bureaucratic improvements, governance excellence",
    "transparency_success": "Transparency achievements, accountability success, open government, transparency progress",
    "crisis_management_success": "Crisis management success, emergency response achievements, disaster management success"
}

# Combined descriptions for backward compatibility
CATEGORY_DESCRIPTIONS = {**ISSUES_DESCRIPTIONS, **POSITIVE_DESCRIPTIONS}

# Non-governance categories to filter out
NON_GOVERNANCE_CATEGORIES = [
    "sports", "entertainment", "celebrities", "personal_life", "gossip", 
    "weather", "purely_social", "non_political", "irrelevant"
]

def get_issues_categories():
    """Return the issues categories (negative/problem-focused)."""
    return ISSUES_CATEGORIES

def get_positive_categories():
    """Return the positive coverage categories (achievement-focused)."""
    return POSITIVE_CATEGORIES

def get_governance_categories():
    """Return all governance categories (combined)."""
    return GOVERNANCE_CATEGORIES

def get_category_description(category_key):
    """Return description for a specific category."""
    return CATEGORY_DESCRIPTIONS.get(category_key, "")

def is_governance_category(category_key):
    """Check if a category is a governance category."""
    return category_key in GOVERNANCE_CATEGORIES

def is_issues_category(category_key):
    """Check if a category is an issues category (negative)."""
    return category_key in ISSUES_CATEGORIES

def is_positive_category(category_key):
    """Check if a category is a positive coverage category."""
    return category_key in POSITIVE_CATEGORIES

def get_category_slug(category_key):
    """Get the slug for a category."""
    return category_key

def get_category_label(category_key):
    """Get the display label for a category."""
    return GOVERNANCE_CATEGORIES.get(category_key, "Unknown Category")

def get_category_type(category_key):
    """Get the type of category (issues, positive, or non_governance)."""
    if category_key in ISSUES_CATEGORIES:
        return "issues"
    elif category_key in POSITIVE_CATEGORIES:
        return "positive"
    else:
        return "non_governance"

def get_federal_ministries():
    """Return all 36 federal ministries."""
    return FEDERAL_MINISTRIES

def get_ministry_subcategories(ministry_key):
    """Return subcategories for a specific ministry."""
    return MINISTRY_SUBCATEGORIES.get(ministry_key, {})

def get_ministry_key_by_name(ministry_name):
    """Get ministry key by ministry name."""
    for key, name in FEDERAL_MINISTRIES.items():
        if name.lower() == ministry_name.lower():
            return key
    return None

def is_federal_ministry(category_key):
    """Check if a category is a federal ministry."""
    return category_key in FEDERAL_MINISTRIES

def get_all_subcategories():
    """Return all subcategories from all ministries."""
    all_subcategories = {}
    for ministry_key, subcategories in MINISTRY_SUBCATEGORIES.items():
        all_subcategories.update(subcategories)
    return all_subcategories

def map_to_closest_category(ai_suggestion: str, sentiment: str = "neutral") -> str:
    """
    Map AI-generated category suggestions to closest predefined federal ministries.
    
    Args:
        ai_suggestion: The category suggested by AI
        sentiment: The sentiment of the content (positive/negative/neutral)
    
    Returns:
        str: The closest predefined federal ministry key
    """
    if not ai_suggestion or ai_suggestion.lower() in ['non_governance', 'unknown', 'irrelevant']:
        return 'non_governance'
    
    ai_lower = ai_suggestion.lower()
    
    # Define mapping rules for common AI suggestions to federal ministries
    mapping_rules = {
        # Education-related
        'education': 'education',
        'educational': 'education',
        'school': 'education',
        'university': 'education',
        'student': 'education',
        'teacher': 'education',
        'learning': 'education',
        
        # Health-related
        'health': 'health_social_welfare',
        'healthcare': 'health_social_welfare',
        'medical': 'health_social_welfare',
        'hospital': 'health_social_welfare',
        'doctor': 'health_social_welfare',
        'medicine': 'health_social_welfare',
        'disease': 'health_social_welfare',
        
        # Infrastructure-related
        'infrastructure': 'works',
        'road': 'works',
        'bridge': 'works',
        'construction': 'works',
        'project': 'works',
        'infrastructure development': 'works',
        
        # Economic-related
        'economy': 'budget_economic_planning',
        'economic': 'budget_economic_planning',
        'finance': 'finance',
        'budget': 'budget_economic_planning',
        'financial': 'finance',
        'money': 'finance',
        'inflation': 'budget_economic_planning',
        'recession': 'budget_economic_planning',
        'growth': 'budget_economic_planning',
        
        # Security-related
        'security': 'interior',
        'crime': 'interior',
        'terrorism': 'interior',
        'violence': 'interior',
        'police': 'police_affairs',
        'law enforcement': 'police_affairs',
        
        # Corruption-related
        'corruption': 'justice',
        'corrupt': 'justice',
        'fraud': 'justice',
        'bribery': 'justice',
        'embezzlement': 'justice',
        
        # Agriculture-related
        'agriculture': 'agriculture_food_security',
        'agricultural': 'agriculture_food_security',
        'farming': 'agriculture_food_security',
        'food': 'agriculture_food_security',
        'crop': 'agriculture_food_security',
        'livestock': 'livestock_development',
        
        # Energy-related
        'energy': 'power',
        'power': 'power',
        'electricity': 'power',
        'oil': 'petroleum_resources',
        'gas': 'petroleum_resources',
        'petroleum': 'petroleum_resources',
        
        # Transportation-related
        'transport': 'transportation',
        'transportation': 'transportation',
        'traffic': 'transportation',
        'vehicle': 'transportation',
        'aviation': 'aviation_aerospace',
        'airline': 'aviation_aerospace',
        'airport': 'aviation_aerospace',
        
        # Housing-related
        'housing': 'housing_urban',
        'house': 'housing_urban',
        'home': 'housing_urban',
        
        # Environment-related
        'environment': 'environment_ecological',
        'environmental': 'environment_ecological',
        'climate': 'environment_ecological',
        'pollution': 'environment_ecological',
        
        # Foreign relations
        'foreign': 'foreign_affairs',
        'diplomacy': 'foreign_affairs',
        'international': 'foreign_affairs',
        
        # Defense-related
        'defense': 'defence',
        'defence': 'defence',
        'military': 'defence',
        'armed forces': 'defence',
        
        # Justice-related
        'justice': 'justice',
        'court': 'justice',
        'legal': 'justice',
        'judiciary': 'justice',
        
        # Social welfare
        'welfare': 'health_social_welfare',
        'poverty': 'humanitarian_poverty',
        'humanitarian': 'humanitarian_poverty',
        
        # Youth-related
        'youth': 'youth_development',
        'young': 'youth_development',
        'unemployment': 'labour_employment',
        'employment': 'labour_employment',
        'job': 'labour_employment',
        'work': 'labour_employment',
        
        # Technology-related
        'technology': 'science_technology',
        'tech': 'science_technology',
        'digital': 'communications_digital',
        'innovation': 'science_technology',
        'cyber': 'communications_digital',
        
        # Electoral-related
        'election': 'special_duties',
        'voting': 'special_duties',
        'democracy': 'special_duties',
        'electoral': 'special_duties',
        
        # Media-related
        'media': 'information_culture',
        'press': 'information_culture',
        'journalism': 'information_culture',
        'information': 'information_culture',
        
        # Trade-related
        'trade': 'industry_trade',
        'commerce': 'industry_trade',
        'business': 'industry_trade',
        'investment': 'industry_trade',
        
        # Gender-related
        'gender': 'women_affairs',
        'women': 'women_affairs',
        'female': 'women_affairs',
        'women affairs': 'women_affairs',
        'women affairs and social development': 'women_affairs',
        
        # Religious-related
        'religion': 'interior',
        'religious': 'interior',
        'faith': 'interior',
        
        # Banking-related
        'banking': 'finance',
        'bank': 'finance',
        'financial sector': 'finance',
        
        # Administration-related
        'administration': 'special_duties',
        'administrative': 'special_duties',
        'government': 'special_duties',
        'governance': 'special_duties',
        'bureaucracy': 'special_duties',
        
        # Transparency-related
        'transparency': 'justice',
        'accountability': 'justice',
        'open government': 'justice',
        
        # Crisis management
        'crisis': 'humanitarian_poverty',
        'emergency': 'humanitarian_poverty',
        'disaster': 'humanitarian_poverty',
        
        # Regional development
        'regional': 'niger_delta',
        'regional development': 'niger_delta',
        'niger delta': 'niger_delta',
        
        # Water-related
        'water': 'water_resources',
        'sanitation': 'water_resources',
        'irrigation': 'water_resources',
        
        # Tourism-related
        'tourism': 'tourism',
        'tourist': 'tourism',
        'hospitality': 'tourism',
        
        # Sports-related
        'sports': 'sports_development',
        'athlete': 'sports_development',
        'sport': 'sports_development',
        
        # Marine-related
        'marine': 'marine_blue_economy',
        'maritime': 'marine_blue_economy',
        'ocean': 'marine_blue_economy',
        'coastal': 'marine_blue_economy',
        
        # Minerals-related
        'minerals': 'solid_minerals',
        'mining': 'solid_minerals',
        'mineral': 'solid_minerals',
        
        # Steel-related
        'steel': 'steel_development',
        'industrialization': 'steel_development',
        
        # FCT-related
        'fct': 'fct_administration',
        'abuja': 'fct_administration',
        'capital': 'fct_administration',
        
        # Art/Culture-related
        'art': 'art_culture_creative',
        'culture': 'art_culture_creative',
        'creative': 'art_culture_creative',
        'heritage': 'art_culture_creative',
        
        # Interior-related (missing mappings)
        'interior': 'interior',
        'internal': 'interior',
        
        # Presidency-related
        'presidency': 'special_duties',
        'president': 'special_duties',
        'executive': 'special_duties',
    }
    
    # Check for exact matches first
    for keyword, ministry in mapping_rules.items():
        if keyword in ai_lower:
            return ministry
    
    # If no match found, return non_governance
    return 'non_governance'
