#!/usr/bin/env python3

import re
import sys
from functools import partial
from multiprocessing import Pool

import spotipy
import yaml
from halo import Halo
from termcolor import cprint
from thefuzz import fuzz
from tidalapi import LoggedInUser
from unidecode import unidecode

from auth import open_tidal_session, open_spotify_session


def simplify(input_string):
    replacements = {
        ' x ': ' ',
        ' vs ': ' ',
        ' - ': ' '
    }
    regex = {
        '(original mix|extended mix|radio edit|mixed|remastered|version)': '',
        '[(]?(ft.|feat.|prod.|[(]with).*\\)|(ft.|feat.|prod.).*': '',
        r'[^a-z0-9$!&?.\'\- ]': ''
    }
    result = unidecode(input_string).lower()
    for k, v in replacements.items():
        result = result.replace(k, v)
    for k, v in regex.items():
        result = re.compile(k).sub(v, result)
    return result


def name_match(tidal_track, spotify_track):
    return fuzz.partial_ratio(simplify(tidal_track.name), simplify(spotify_track['name'])) >= 90


def artist_match(tidal_track, spotify_track):
    def get_tidal_artists(tidal_track):
        result = ''
        for artist in tidal_track.artists:
            result += artist.name + ' '
        return simplify(result)

    def get_spotify_artists(spotify_track):
        result = ''
        for artist in spotify_track['artists']:
            result += artist['name'] + ' '
        return simplify(result)

    return fuzz.token_set_ratio(get_tidal_artists(tidal_track), get_spotify_artists(spotify_track)) >= 80


def duration_match(tidal_track, spotify_track, tolerance=2):
    return abs(tidal_track.duration - spotify_track['duration_ms'] / 1000) < tolerance


def album_match(tidal_track, spotify_track):
    return fuzz.ratio(simplify(tidal_track.album.name), simplify(spotify_track['album']['name'])) >= 90


def match(tidal_track, spotify_track):
    name_matching = name_match(tidal_track, spotify_track)
    artist_matching = artist_match(tidal_track, spotify_track)
    duration_matching = duration_match(tidal_track, spotify_track)
    album_matching = album_match(tidal_track, spotify_track)

    return [name_matching, artist_matching, duration_matching, album_matching].count(True) >= 3


def tidal_search(spotify_track, tidal_session):
    query = simplify(spotify_track['name'])
    if len(query) <= 25:
        query = simplify(spotify_track['artists'][0]['name']) + ' ' + simplify(spotify_track['name'])
    for track in tidal_session.search(query)['tracks']:
        if match(track, spotify_track):
            return track


@Halo(text='Sync in progress...', spinner='dots')
def set_tidal_playlist(session, playlist_id, track_ids):
    playlist = session.playlist(playlist_id)
    playlist.add(list(track_ids))


@Halo(text='Searching for tracks on Tidal...', spinner='dots')
def call_async(spotify_tracks, **kwargs):
    results = len(spotify_tracks) * [None]
    with Pool(50) as pool:
        for index, result in enumerate(pool.map(partial(tidal_search, **kwargs), spotify_tracks)):
            results[index] = result
    return results


def get_tracks_from_spotify_playlist(spotify_session, spotify_playlist):
    output = []
    results = spotify_session.playlist_tracks(spotify_playlist['id'],
                                              fields="next,items(track(name,artists(name),duration_ms,album(name)))")
    while True:
        output.extend([r['track'] for r in results['items'] if r['track'] is not None])
        if results['next']:
            results = spotify_session.next(results)
        else:
            return output


def sync_playlist(spotify_session, tidal_session, spotify_playlist, tidal_playlist):
    tidal_track_ids = []
    spotify_tracks = get_tracks_from_spotify_playlist(spotify_session, spotify_playlist)
    tidal_tracks = call_async(spotify_tracks, tidal_session=tidal_session)
    for index, tidal_track in enumerate(tidal_tracks):
        if tidal_track:
            tidal_track_ids.append(tidal_track.id)
        else:
            cprint(" -> track n.{} not found".format(index + 1), 'yellow')
    set_tidal_playlist(tidal_session, tidal_playlist.id, tidal_track_ids)


def sync_list(spotify_session, tidal_session, config):
    tidal_user = LoggedInUser(tidal_session, tidal_session.user.id)
    tidal_playlists = tidal_user.playlists()
    for index, spotify_id in enumerate(config['sync_playlists']):
        try:
            spotify_playlist = spotify_session.playlist(spotify_id)
        except spotipy.SpotifyException:
            cprint("Unable to get Spotify playlist with id: {}".format(spotify_id), 'red')
            continue

        if any(tidal_playlist.name == spotify_playlist['name'] for tidal_playlist in tidal_playlists):
            tidal_session.playlist(next((tidal_playlist for tidal_playlist in tidal_playlists if
                                         tidal_playlist.name == spotify_playlist['name'])).id).delete()

        tidal_playlist = tidal_user.create_playlist(spotify_playlist['name'], spotify_playlist['description'])
        cprint('\u25B6 Spotify playlist ({}/{}): {}'.format(index + 1,
                                                            len(config['sync_playlists']), spotify_playlist['name']),
               'magenta')
        sync_playlist(spotify_session, tidal_session, spotify_playlist, tidal_playlist)
        cprint('Sync completed.', 'green')


if __name__ == '__main__':
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)
    spotify_session = open_spotify_session(config['spotify'])
    tidal_session = open_tidal_session()
    if not tidal_session.check_login():
        cprint('Tidal: connection failed.', 'red')
        sys.exit()
    if config['sync_playlists'] is not None:
        sync_list(spotify_session, tidal_session, config)
    else:
        cprint('Please add Spotify playlist IDs to the config file first.', 'yellow')
        sys.exit()
