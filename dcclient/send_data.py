import enum
from pydantic import BaseModel, Json, model_validator
from typing import List
from enum import Enum


class MatchModel(BaseModel):
    """To get match_id from server"""
    time_limit: int
    extra_end_time_limit: int
    standard_end_count: int
    match_name: str


class ScoreModel(BaseModel):
    first_team_score: List[int]
    second_team_score: List[int]


class PhysicalSimulatorModel(BaseModel):
    simulator_name: str


class TournamentModel(BaseModel):
    tournament_name: str


class ShotInfoModel(BaseModel):
    translational_velocity: float
    angular_velocity: float | None
    shot_angle: float


class StateModel(BaseModel):
    end_number: int
    shot_number: int
    total_shot_number: int


class StoneCoordinates(BaseModel):
    stone_data: Json


class MatchNameModel(str, Enum):
    team0 = "team0"         # team0 is first attacker team at the first end
    team1 = "team1"         # team1 is sencond attacker team at the first end


class PlayerModel(BaseModel):
    max_velocity: float
    shot_std_dev: float
    angle_std_dev: float
    player_name: str


class TeamModel(BaseModel):
    use_default_config: bool
    team_name: str                  # your team name
    match_team_name: MatchNameModel = MatchNameModel.team1  # team0 or team1
    player1: PlayerModel
    player2: PlayerModel
    # For Mix Doubles, player3/player4 can be omitted or set to None.
    player3: PlayerModel | None = None
    player4: PlayerModel | None = None


class GameMode(str, Enum):
    standard = "standard"
    mix_doubles = "mix_doubles"


class MixDoublesTeamModel(BaseModel):
    """Team configuration for Mix Doubles.

    Note:
        Current 4-person team config uses player1..player4.
        Mix Doubles typically uses 2 players, so this model is provided for clients
        that want to represent that explicitly.
    """

    use_default_config: bool
    team_name: str
    match_team_name: MatchNameModel = MatchNameModel.team1
    player1: PlayerModel
    player2: PlayerModel


class PositionedStonesModel(str, enum.Enum):
    center_guard = "center_guard"
    center_house = "center_house"
    pp_left = "pp_left"
    pp_right = "pp_right"


class ClientDataModel(BaseModel):
    game_mode: GameMode = GameMode.standard
    tournament: TournamentModel
    simulator: PhysicalSimulatorModel
    applied_rule: str
    time_limit: float
    extra_end_time_limit: float
    standard_end_count: int
    match_name: str

    # Only used for Mix Doubles. For standard games, set null (None).
    # The server-side meaning can be either pattern-id or a future expanded structure.
    positioned_stones_pattern: int | None = None

    @model_validator(mode="after")
    def _validate_game_mode_and_pattern(self):
        if self.game_mode == GameMode.mix_doubles:
            if self.positioned_stones_pattern is None:
                raise ValueError(
                    "positioned_stones_pattern is required when game_mode is mix_doubles"
                )
        else:
            if self.positioned_stones_pattern is not None:
                raise ValueError(
                    "positioned_stones_pattern must be null when game_mode is not mix_doubles"
                )
        return self



