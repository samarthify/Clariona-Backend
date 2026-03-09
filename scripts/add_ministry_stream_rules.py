#!/usr/bin/env python3
"""Add ministry X stream rules to x_stream_rules. Run sync_x_stream_rules.py after."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env", override=False)

from api.database import SessionLocal
from api.models import XStreamRule

SUFFIX = " lang:en -is:retweet"

RULES = [
    ("finance_ministry", [
        '"Finance Minister Nigeria"', '"Nigeria fiscal policy"', '"Nigeria budget allocation"',
        '"Nigeria revenue generation"', '"Nigeria tax reform"', '"Nigeria debt management"',
        '"Nigeria macroeconomic stability"', '"Nigeria public financial management"',
        '"Nigeria capital markets"', '"Nigeria economic stimulus"', '"Nigeria Treasury"',
    ]),
    ("trade_investment_ministry", [
        '"Trade and Investment Ministry Nigeria"', '"trade facilitation Nigeria"',
        '"foreign direct investment Nigeria"', '"FDI Nigeria"', '"export promotion Nigeria"',
        '"ease of doing business Nigeria"', '"special economic zones Nigeria"', '"SEZ Nigeria"',
        '"trade agreements Nigeria"', '"investor relations Nigeria"', '"market access Nigeria"',
        '"competitiveness Nigeria"',
    ]),
    ("fmiti_ministry", [
        '"FMITI Nigeria"', '"Federal Ministry of Industry Trade and Investment"',
        '"Jumoke Oduwole"', '"NIPC Nigeria"', '"NEPC Nigeria"', '"NEPZA Nigeria"',
        '"AfCFTA Nigeria"', '"PEBEC Nigeria"', '"SMEDAN Nigeria"', '"ease of doing business Nigeria"',
        '"pioneer status Nigeria"', '"free trade zone Nigeria"', '"export expansion grant"',
    ]),
    ("economic_planning_ministry", [
        '"Ministry of Economic Planning Nigeria"', '"national development plan Nigeria"',
        '"sustainable development goals Nigeria"', '"SDGs Nigeria"', '"economic diversification Nigeria"',
        '"strategic planning Nigeria"', '"performance indicators Nigeria"', '"sectoral growth Nigeria"',
        '"data-driven policy Nigeria"', '"mid-term expenditure framework Nigeria"',
    ]),
    ("agriculture_ministry", [
        '"Agriculture Ministry Nigeria"', '"Ministry of Rural Development Nigeria"',
        '"agribusiness Nigeria"', '"value chain development Nigeria"', '"rural entrepreneurship Nigeria"',
        '"farmer access to credit Nigeria"', '"agricultural cooperative development Nigeria"',
        '"non-oil exports Nigeria"', '"rural infrastructure Nigeria"', '"poverty reduction Nigeria"',
        '"food security Nigeria"', '"agricultural mechanization Nigeria"', '"Seeds Nigeria"',
        '"fertilizer Nigeria"', '"irrigation Nigeria"', '"agricultural extension services Nigeria"',
        '"crop yield Nigeria"', '"livestock development Nigeria"', '"fisheries Nigeria"',
        '"agro-processing Nigeria"',
    ]),
    ("interior_ministry", [
        '"Interior Ministry Nigeria"', '"internal security Nigeria"', '"civil defense Nigeria"',
        '"border management Nigeria"', '"national identity Nigeria"', '"community policing Nigeria"',
        '"conflict resolution Nigeria"', '"fire and rescue services Nigeria"', '"public order Nigeria"',
        '"citizenship Nigeria"',
    ]),
    ("defence_ministry", [
        '"Defence Ministry Nigeria"', '"national defense Nigeria"', '"armed forces Nigeria"',
        '"military modernization Nigeria"', '"counter-terrorism Nigeria"', '"peacekeeping Nigeria"',
        '"territorial integrity Nigeria"', '"civil-military relations Nigeria"', '"military intelligence Nigeria"',
    ]),
    ("police_affairs_ministry", [
        '"Police Affairs Ministry Nigeria"', '"police reform Nigeria"', '"crime prevention Nigeria"',
        '"law enforcement Nigeria"', '"police welfare Nigeria"', '"police training Nigeria"',
        '"police capacity building Nigeria"', '"police oversight Nigeria"', '"police accountability Nigeria"',
        '"community trust police Nigeria"',
    ]),
    ("humanitarian_ministry", [
        '"Humanitarian Affairs Ministry Nigeria"', '"disaster risk reduction Nigeria"',
        '"emergency response Nigeria"', '"social safety nets Nigeria"', '"conditional cash transfers Nigeria"',
        '"vulnerability mapping Nigeria"', '"humanitarian coordination Nigeria"', '"social protection Nigeria"',
        '"resilience building Nigeria"',
    ]),
    ("education_ministry", [
        '"Education Ministry Nigeria"', '"curriculum reform Nigeria"', '"teacher training Nigeria"',
        '"STEM education Nigeria"', '"inclusive education Nigeria"', '"basic education Nigeria"',
        '"tertiary education Nigeria"', '"literacy rate Nigeria"', '"education financing Nigeria"',
        '"education accreditation Nigeria"', '"digital learning Nigeria"',
    ]),
    ("youth_sports_ministry", [
        '"Youth and Sports Ministry Nigeria"', '"skills acquisition Nigeria"',
        '"vocational training Nigeria"', '"entrepreneurship training Nigeria"', '"youth empowerment Nigeria"',
        '"talent development Nigeria"', '"sports infrastructure Nigeria"', '"non-formal education Nigeria"',
        '"mentorship programs Nigeria"',
    ]),
    ("science_technology_ministry", [
        '"Science and Technology Ministry Nigeria"', '"research and development Nigeria"',
        '"R&D Nigeria"', '"innovation hubs Nigeria"', '"technology transfer Nigeria"',
        '"scholarship schemes Nigeria"', '"science education Nigeria"', '"patents Nigeria"',
        '"research commercialization Nigeria"', '"artificial intelligence Nigeria"', '"AI Nigeria"',
        '"blockchain Nigeria"', '"Internet of Things Nigeria"', '"IoT Nigeria"', '"software development Nigeria"',
        '"technology incubation Nigeria"', '"ICT research Nigeria"', '"digital innovation Nigeria"',
    ]),
    ("health_ministry", [
        '"Health Ministry Nigeria"', '"universal health coverage Nigeria"', '"UHC Nigeria"',
        '"primary healthcare Nigeria"', '"disease prevention Nigeria"', '"health infrastructure Nigeria"',
        '"maternal and child health Nigeria"', '"immunization Nigeria"', '"health insurance Nigeria"',
        '"NHIS Nigeria"', '"medical personnel Nigeria"', '"pandemic preparedness Nigeria"',
    ]),
    ("women_affairs_ministry", [
        '"Ministry of Women Affairs Nigeria"', '"gender-based violence prevention Nigeria"',
        '"maternal health Nigeria"', '"women economic empowerment Nigeria"', '"girl child education Nigeria"',
        '"gender equality Nigeria"', '"social welfare Nigeria"', '"childcare support Nigeria"',
    ]),
    ("environment_ministry", [
        '"Environment Ministry Nigeria"', '"sanitation Nigeria"', '"clean water access Nigeria"',
        '"pollution control Nigeria"', '"waste management Nigeria"', '"climate resilience Nigeria"',
        '"environmental health Nigeria"', '"urban greenery Nigeria"', '"climate change mitigation Nigeria"',
        '"net zero Nigeria"', '"carbon credits Nigeria"', '"sustainable energy Nigeria"',
        '"green economy Nigeria"', '"environmental impact assessment Nigeria"',
    ]),
    ("works_housing_ministry", [
        '"Works and Housing Ministry Nigeria"', '"public works Nigeria"', '"road construction Nigeria"',
        '"housing schemes Nigeria"', '"affordable housing Nigeria"', '"building standards Nigeria"',
        '"maintenance culture Nigeria"', '"construction industry Nigeria"', '"urban development Nigeria"',
    ]),
    ("transportation_ministry", [
        '"Transportation Ministry Nigeria"', '"multimodal transport Nigeria"', '"railway modernization Nigeria"',
        '"airport development Nigeria"', '"port efficiency Nigeria"', '"road safety Nigeria"',
        '"public transit Nigeria"', '"logistics Nigeria"', '"national carrier Nigeria"',
    ]),
    ("power_ministry", [
        '"Power Ministry Nigeria"', '"grid expansion Nigeria"', '"transmission infrastructure Nigeria"',
        '"rural electrification Nigeria"', '"power generation Nigeria"', '"distribution networks Nigeria"',
        '"electricity metering Nigeria"', '"renewable energy Nigeria"', '"renewable energy integration Nigeria"',
        '"solar power projects Nigeria"', '"grid stability Nigeria"', '"off-grid solutions Nigeria"',
        '"energy efficiency Nigeria"',
    ]),
    ("petroleum_ministry", [
        '"Petroleum Resources Ministry Nigeria"', '"gas commercialization Nigeria"',
        '"flare gas reduction Nigeria"', '"LNG Nigeria"', '"liquefied natural gas Nigeria"',
        '"decarbonization Nigeria"', '"biofuels Nigeria"', '"carbon capture Nigeria"',
        '"upstream diversification Nigeria"',
    ]),
    ("water_resources_ministry", [
        '"Water Resources Ministry Nigeria"', '"Ministry of Water Resources Nigeria"',
        '"irrigation schemes Nigeria"', '"water management Nigeria"', '"dams and reservoirs Nigeria"',
        '"sustainable water use Nigeria"', '"river basin development Nigeria"',
    ]),
    ("communications_digital_ministry", [
        '"Communication and Digital Economy Ministry Nigeria"', '"broadband penetration Nigeria"',
        '"digital inclusion Nigeria"', '"fintech Nigeria"', '"e-governance Nigeria"',
        '"digital literacy Nigeria"', '"startup ecosystem Nigeria"', '"data protection Nigeria"',
        '"cybersecurity Nigeria"', '"digital ID Nigeria"',
    ]),
]


def main():
    db = SessionLocal()
    added = 0
    skipped = 0
    try:
        existing_tags = {r.tag for r in db.query(XStreamRule).filter(XStreamRule.is_active == True).all() if r.tag}
        for tag, keywords in RULES:
            if tag in existing_tags:
                print(f"Skip (exists): {tag}")
                skipped += 1
                continue
            value = "(" + " OR ".join(keywords) + ")" + SUFFIX
            if len(value) > 1024:
                print(f"Skip (too long {len(value)}): {tag}")
                skipped += 1
                continue
            rule = XStreamRule(value=value, tag=tag, is_active=True)
            db.add(rule)
            db.commit()
            print(f"Added: {tag} ({len(value)} chars)")
            added += 1
            existing_tags.add(tag)
    finally:
        db.close()
    print(f"\nDone. Added {added}, skipped {skipped}")


if __name__ == "__main__":
    main()
