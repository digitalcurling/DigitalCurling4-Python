from pydantic import BaseModel, Json
from typing import Optional, Dict, List
from uuid import UUID
from datetime import datetime


class TournamentSchema(BaseModel):
    tournament_id: UUID
    tournament_name: str

    class Config:
        from_attributes = True


class PhysicalSimulatorSchema(BaseModel):
    physical_simulator_id: UUID
    simulator_name: str

    class Config:
        from_attributes = True


class PlayerSchema(BaseModel):
    player_id: UUID
    max_velocity: float
    shot_dispersion_rate: float
    player_name: str


class TrajectorySchema(BaseModel):
    trajectory_id: UUID
    trajectory_data: Json


class CoordinateDataSchema(BaseModel):
    x: float
    y: float

    class Config:
        from_attributes = True


class StoneCoordinateSchema(BaseModel):
    data: Dict[str, List[CoordinateDataSchema]]

    class Config:
        from_attributes = True


class ScoreSchema(BaseModel):
    team0: list
    team1: list

    class Config:
        from_attributes = True


class ShotInfoSchema(BaseModel):
    translational_velocity: float
    angular_velocity: float
    shot_angle: float


class PowerPlayEndSchema(BaseModel):
    team0: int | None = None
    team1: int | None = None


class MixDoublesSettingsSchema(BaseModel):
    end_setup_team: str
    positioned_stones_pattern: int
    power_play_end: PowerPlayEndSchema

class StateSchema(BaseModel):
    winner_team: str | None
    end_number: int
    shot_number: int | None
    total_shot_number: int | None
    next_shot_team: str | None
    first_team_remaining_time: float
    second_team_remaining_time: float
    first_team_extra_end_remaining_time: float
    second_team_extra_end_remaining_time: float
    mix_doubles_settings: Optional[MixDoublesSettingsSchema] = None
    last_move: ShotInfoSchema | None
    stone_coordinate: Optional[StoneCoordinateSchema] = None
    score: Optional[ScoreSchema] = None

    class Config:
        from_attributes = True


class MatchDataSchema(BaseModel):
    match_id: UUID
    first_team_id: UUID
    second_team_id: UUID
    score_id: UUID
    time_limit: int
    extra_end_time_limit: int
    standard_end_count: int
    physical_simulator_id: UUID
    tournament_id: UUID
    match_name: str
    created_at: datetime
    started_at: datetime
    score: Optional[ScoreSchema] = None
    tournament: Optional[TournamentSchema] = None
    simulator: Optional[PhysicalSimulatorSchema] = None

    class Config:
        from_attributes = True
