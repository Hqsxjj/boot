from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from .database import AppDataBase

class MissingEpisode(AppDataBase):
    __tablename__ = 'missing_episodes'

    id = Column(String, primary_key=True)  # series_id + "_" + season_number
    series_id = Column(String, index=True)
    series_name = Column(String)
    season_number = Column(Integer)
    total_episodes = Column(Integer)
    local_episodes = Column(Integer)
    missing_items = Column(String)  # E01, E02 from original logic
    poster_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.series_name,
            'seriesId': self.series_id,
            'season': self.season_number,
            'totalEp': self.total_episodes,
            'localEp': self.local_episodes,
            'missing': self.missing_items,
            'poster': self.poster_path,
            'checkDate': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
