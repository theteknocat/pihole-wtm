from pydantic import BaseModel


class TrackerInfo(BaseModel):
    tracker_name: str
    category: str
    company_name: str | None = None
    company_country: str | None = None
