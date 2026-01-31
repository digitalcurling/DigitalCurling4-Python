# DigitalCurling IO

## Input(投球情報)

- **match_id**: `UUID`  
  各試合固有のID

- **translational_velocity**: `float`  
  並進速度

- **angular_velocity_sign**: `str`  
  回転方向を示す。値は `"cw"` または `"ccw"`

- **angular_velocity**: `float`  
  角速度

- **shot_angle**: `float`  
  投球時に打ち出すストーンの角度  
  (長手方向をy軸とし、y軸を90°とした際の角度)


## Output(盤面情報)

> 前提として、最初のエンドにおいて先攻だったチームに `"team0"`、後攻だったチームに `"team1"` という名前をサーバから各クライアントに割り当てています

- **winner_team**: `str | None`  
  勝利したチーム名、またはなし

- **end_number**: `int`  
  最初のエンドを 0 としてカウントしたエンド数

- **shot_number**: `int`  
  Output を送信する前に投球情報を送信したチームの、そのエンドにおけるショット数 (0～7)

- **total_shot_number**: `int`  
  そのエンドにおける両チーム合わせたショット数 (0～15)

- **first_team_remaining_time**: `float`  
  最初のエンドにおいて先攻(team0)の残りの思考時間

- **second_team_remaining_time**: `float`  
  最初のエンドにおいて後攻(team1)の残りの思考時間

- **first_team_extra_remaining_time**: `float`  
  最初のエンドにおいて先攻(team0)の延長戦における残りの思考時間

- **second_team_extra_remaining_time**: `float`  
  最初のエンドにおいて後攻(team1)の延長戦における残りの思考時間

- **stone_coordinate**: `dict`  
  各チームのストーン配置  
  例:
  ```json
    {
    "team0": [
      {"x": 0.9273043870925903, "y": 37.281089782714844},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0}
    ],
    "team1": [
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0}
    ]
  }
  ```
  なお、各ストーンのxyデータは全てfloat

- **score**
```python
{
    'first_team_score': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'second_team_score': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
}
```
なお、各スコアは全てint

### Output全体像

```json
{
  "winner_team": "team0",
  "end_number": 0,
  "shot_number": 1,
  "total_shot_number": 2,
  "next_shot_team": "team1",
  "first_team_remaining_time": 120.0,
  "second_team_remaining_time": 110.0,
  "first_team_extra_end_remaining_time": 30.0,
  "second_team_extra_end_remaining_time": 25.0,
  "stone_coordinate_data": {
    "team0": [
      {"x": 0.9273043870925903, "y": 37.281089782714844},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0}
    ],
    "team1": [
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0},
      {"x": 0.0, "y": 0.0}
    ]
  },
  "score": {
    "first_team_score": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "second_team_score": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  }
}
```