import random
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.world import WorldNode

router = APIRouter()


@router.post("/")
def create_campaign(db: Session = Depends(get_db)):
    campaign = Campaign(
        name="Hardcoded Campaign",
        seed=random.randint(1, 999999),
        tone_vector={
            "bleakness": 0.2,
            "hope": 0.5,
            "mysticism": 0.3,
            "political": 0.2,
        },
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Create region
    region = WorldNode(
        campaign_id=campaign.id,
        node_type="region",
        name="Starter Region",
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    # Create tavern
    tavern = WorldNode(
        campaign_id=campaign.id,
        parent_id=region.id,
        node_type="location",
        name="The Rusty Flagon",
    )
    db.add(tavern)
    db.commit()
    db.refresh(tavern)

    return {
        "campaign_id": str(campaign.id),
        "region_id": str(region.id),
        "tavern_id": str(tavern.id),
    }
