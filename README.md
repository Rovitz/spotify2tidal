A python script for importing Spotify playlists into Tidal

Installation
-----------
Clone this git repository and then run:

```bash
python -m pip install -r requirements.txt
```

Setup
-----

0. Go [here](https://developer.spotify.com/documentation/general/guides/authorization/app-settings/) and register a new app on developer.spotify.com.
1. Rename the file example_config.yml to config.yml
2. Copy and paste your client ID and client secret to the Spotify part of the config file
3. Copy and paste the value in 'redirect_uri' of the config file to Redirect URIs at developer.spotify.com and press ADD
4. Enter your Spotify username to the config file
5. Add your playlist IDs to the config file

Usage
----
To sync Spotify playlists with your Tidal account run the following

```bash
python sync.py
```

Enjoy!

Credits
------
### [ timrae / spotify_to_tidal](https://github.com/timrae/spotify_to_tidal)