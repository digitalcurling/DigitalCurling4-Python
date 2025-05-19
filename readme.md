# New Client For Digital Curling

This is a new client for digital curling.

## Install requirements.txt
```bash
pip install -r requirements.txt
```

We plan to release this repository on pypi eventually, but currently use
```bash
pip install .
```

## How to use
### Prepare user data
Each user must be registered on the server side for the match to take place. 
e.g.:
```
MATCH_USER_NAME="user"
PASS_WORD="password"
```
In this trial stage, the database where users are registered is shared on the server side, so I think you can play against each other soon.
(In the production environment, the user will be given a user name and password in advance, and the user will be registered on the server.)

Note that the user name and password already registered are in the .env of this shared repository.


### Make Match
In the "src.setting.json" file,  describe the information required for the match, such as the **standard_end_count**, **simulator** to be used, **time_limits**, etc.
(Currently, “fcv1” is the only simulator available, so matches cannot be played on other simulators.)
After completing the settings in setting.json, enter the following command.
```bash
cd src
python match_maker.py
```
The above command should be entered when you want to start a new match.

The match_id will now be stored in match_id.json.

### Connect client to server
I prepared folders named client0 and client1 so that we could actually play against each other.(When distributing, delete the client0 and client1 folders and refer to sample_client.py)

You can configure the players who will play in that match in “client0.team0_config.json” and “client1.team1_config.json”. In addition, when playing with the same settings as in the tournament, you can set
```md
"use_default_config": true
``` 
If you want to create a unique team,

```md
"use_default_config": flase
``` 

After the above settings are in place, connect the client to the server by entering the following command

```bash
cd client0
python client.py
```

Then open another terminal,
```bash
cd client1
python client.py
```

I think you can check the connection with these command.

