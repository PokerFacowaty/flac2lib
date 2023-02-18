import argparse
import cv2
import shutil
import sys
import yaml
import webbrowser
from pathlib import Path
from pydub import AudioSegment
from pydub.utils import mediainfo
from urllib.parse import urlencode
from urllib.request import urlopen

# DONE: sorted imports
# DONE: argparse
# DONE: ? config parsing as a function separate from main?
# DONE: process_album uses a fuckton of variables, some of them from
# AlbumToProcess, maybe it can be used?
# AlbumToProccess is created in that function, so no, but solved with cfg
# DONE: skipping question about more albums when there was source / dst path
# specified in an argument (since you're only converting one then)
# TODO: variable names to simplify / shorten
# DONE: whiles for inputs, so only particular inputs are accepted and nothing
# happens for others - either implement everywhere or change;
# implementing everywhere + validation
# DONE: test if all of them are breaking properly
# DONE: consistent prints
# DONE: if entire first makes more sense in 214
# DONE: lowercase "tag" in get_dst_album_path?
# along with a new sytem for tags with looping over all possibilities
# DONE: 295 and more - only spaces should still be considered as blank
# DONE: get_dst_album_path also returns artist and album name which is
# misleading
# Added a proper docstring since it's easier than refactoring.
# DONE: proper comments / docstrings
# DONE: type hints
# DONE: input validations from inpit-validation-notes
# just need testing


class AlbumToProcess:
    def __init__(self, dst_album_path, song_picks_paths, flac_album_path,
                 ffmpeg_params, dst_format, is_compilation):
        self.dst_path = dst_album_path
        self.picks_paths = song_picks_paths
        self.flac_path = flac_album_path
        self.ffmpeg_params = ffmpeg_params
        self.dst_format = dst_format
        self.is_compilation = is_compilation


queue = []


def main():
    '''Parses the config file with the help of parse_args_and_config and
       initiates a loop of calling process_album() until the user decides
       they're done with choosing albums, then proceeds to convert all the
       albums in the queue.'''

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default=None,
                        help="point to a specific yaml config file")
    parser.add_argument("-s", "--source", default=None,
                        help="provide the source album folder", type=str)
    parser.add_argument("-d", "--destination", default=None,
                        help="provide the destination folder", type=str)
    parser.add_argument("-e", "--entire", action="store_true", default=None,
                        help="convert an entire folder")
    parser.add_argument("-l", "--latest", action="store_true", default=None,
                        help="convert the most recently modified folder")
    parser.add_argument("--skip-cover-art", action="store_true", default=None,
                        help="skip copying the cover art")
    parser.add_argument("--skip-dir-prompts", action="store_true",
                        help="use ARTIST and ALBUM tags for directory names"
                        + "without asking", default=None)
    parser.add_argument("--compilation", action="store_true",
                        help="mark the album(s) as compilation(s) and skip the"
                        + "prompt")
    parser.add_argument("--not-compilation", action="store_true",
                        help="mark the album(s) as not compilation(s) and skip"
                        + "the prompt")
    args = parser.parse_args()

    cfg = parse_args_and_config(args)

    print("\n----- flac2lib.py by PokerFacowaty -----")
    print("https://github.com/PokerFacowaty/flac2lib")

    while process_album(cfg):
        # process_album returns True or False depending on the answer to the
        # question whether the user wants to add another album
        continue

    for album in queue:
        convert_songs(album)


def parse_args_and_config(args) -> dict:
    '''Merges the config file and args into a cfg dict that is later used
       wherever config is needed'''

    cfg = dict()

    if args.config is None:
        config_file = 'config.yaml'
    else:
        config_file = args.config
    yaml_config = yaml.safe_load(open(config_file))

    if args.source is None:
        cfg["flac_album_path"] = None
    else:
        cfg["flac_album_path"] = args.source

    if args.destination is None:
        cfg["dst_album_path"] = None
    else:
        cfg["dst_album_path"] = args.destination

    if args.entire is None:
        cfg["entire"] = yaml_config["entire"]
    else:
        cfg["entire"] = args.entire

    if args.latest is None:
        cfg["latest"] = yaml_config["latest"]
    else:
        cfg["latest"] = args.latest

    if args.skip_cover_art is None:
        cfg["cover_art"] = yaml_config["get_cover_art"]
    elif args.skip_cover_art:
        cfg["cover_art"] = False

    if args.skip_dir_prompts is None:
        cfg["dir_prompts"] = yaml_config["dir_name_prompts"]
    elif args.skip_dir_prompts:
        cfg["dir_prompts"] = False

    if args.compilation is None and args.not_compilation is None:
        cfg["is_compilation"] = None
    elif args.compilation:
        cfg["is_compilation"] = True
    else:
        cfg["is_compilation"] = False

    cfg["flac_albums_dir"] = Path(yaml_config["flac_albums_dir"])
    cfg["dst_albums_dir"] = Path(yaml_config["dst_albums_dir"])
    cfg["num_albums_to_show"] = yaml_config["num_albums_to_show"]
    cfg["default_cover_art_name"] = yaml_config["default_cover_art_name"]
    cfg["cover_art_suffixes"] = yaml_config["cover_art_suffixes"]
    cfg["dst_format"] = yaml_config["destination_format"]
    cfg["ffmpeg_params"] = yaml_config["ffmpeg_params"]

    return cfg


def process_album(cfg) -> bool:
    '''Gets all the info that is needed about the album and stores it in an
       AlbumToProcess object inside the queue list.'''

    single_album = False
    if cfg["flac_album_path"] is None:
        cfg["flac_album_path"] = get_flac_album_path(cfg["flac_albums_dir"],
                                                     cfg["num_albums_to_show"],
                                                     cfg["latest"])
    else:
        single_album = True

    if cfg["is_compilation"] is None:
        cfg["is_compilation"] = ask_if_compilation()

    cfg["song_picks_paths"] = pick_songs(cfg["flac_album_path"], cfg["entire"])

    if cfg["dst_album_path"] is None:
        (cfg["artist_name"],
         cfg["album_name"],
         cfg["dst_album_path"]) = get_dst_album_path(cfg["song_picks_paths"],
                                                     cfg["dst_albums_dir"],
                                                     cfg["dir_prompts"])
    else:
        single_album = True

    if cfg["cover_art"]:
        get_cover_art(cfg)

    queue.append(AlbumToProcess(cfg["dst_album_path"], cfg["song_picks_paths"],
                                cfg["flac_album_path"], cfg["ffmpeg_params"],
                                cfg["dst_format"], cfg["is_compilation"]))

    if single_album:
        return False

    while True:
        answer = input("\nWould you like to add more albums? [y/n]\n")
        if answer.lower() == "y":
            return True
        elif answer.lower() == "n":
            return False


def get_flac_album_path(flac_albums_dir, num_albums_to_show, latest) -> Path:
    '''Fetches folders inside flac_albums_dir containing flac files (note that
       with multi-CD albums, each CD is treated as a separate album since that
       is the best way of dealing with those I thought of), sorts them
       by their modification time, takes user input on which one should be
       chosen; returns the first one without asking if 'latest' is set
       to True'''

    folders_with_flacs = []
    for x in flac_albums_dir.rglob("*"):
        if x.suffix == ".flac" and x.parent not in folders_with_flacs:
            folders_with_flacs.append(x.parent)

    # sorts the albums by their modification time, most recent first
    folder_paths_to_show = sorted(folders_with_flacs, key=lambda
                                  x: x.lstat().st_mtime, reverse=True)

    if latest:
        return folder_paths_to_show[0]

    print("\n\n--- Albums ---\n")
    rel_folder_paths_to_show = [x.relative_to(flac_albums_dir)
                                for x in folder_paths_to_show]

    for i in range(min(len(folder_paths_to_show), num_albums_to_show)):
        print(f"{i}: ", str(rel_folder_paths_to_show[i]))

    while True:
        answer = input("\nChoose the album\n:")
        if (answer.isnumeric()
           and int(answer) < (min(len(folder_paths_to_show),
                                  num_albums_to_show))):
            return folder_paths_to_show[int(answer)]


def ask_if_compilation() -> bool:
    print("\n\n--- Compilation ---\n")
    print("Is the album a compilation? (adds compilation = 1 to the tags)")
    print("[y] / [n]")
    while True:
        answer = input(':')
        if answer.lower() == "y":
            return True
        elif answer.lower() == "n":
            return False


def pick_songs(flac_album_path, entire) -> list:
    '''Fetches all the flac files found in the album path, takes user input
       on which ones should be chosen and returns the paths for those. Returns
       all paths found if 'entire' is set to True.'''

    all_flac_files_paths = list(flac_album_path.rglob("*.flac"))

    if entire:
        song_picks = list(range(len(all_flac_files_paths)))
    else:
        print("\n\n--- Songs ---\n")
        for nr, f in enumerate(sorted([x.name for x in all_flac_files_paths])):
            print(nr, ": ", f)
        print()

        while True:
            answer = input("Choose songs, comma separated\n:")

            valid = True
            if len(answer.split(",")) > len(all_flac_files_paths):
                valid = False
            else:
                # no point in even starting this loop if the list is longer
                for num in answer.split(","):
                    if not num.isnumeric():
                        valid = False
                        break
                    elif int(num) >= len(all_flac_files_paths):
                        valid = False
                        break

            if valid:
                break
            else:
                print("Invalid input\n")
                continue
        song_picks = [int(x) for x in str(answer).split(',')]
    return [all_flac_files_paths[x] for x in song_picks]


def get_dst_album_path(song_picks_paths, dst_albums_dir, dir_prompts):
    '''Proposes an artist/album combo for the destination dir and subdir names
       based on the flac's metadata. Takes confirmation or custom names as
       input. Asks if there is an additional folder needed (such as 'CD1' for
       multi-CD albums), since doing so automatically would be overly complex
       and only cover some cases. The asking proccess is obviously skipped
       if the --skip-dir-prompts argument is used. Constructs and returns
       a full destination folder path. Also returns artist_name and
       album_name since these are established in the process.'''

    # This looping is so that it covers all possibilities of the spelling I
    # could think of. 'TAG' and 'ARTIST' covered most cases initially, but then
    # I came across an exception that would break everything.
    artist_name = None
    album_name = None
    for t in ['TAG', 'tag', 'Tag']:
        for ar in ['ARTIST', 'artist', 'Artist']:
            if (t in mediainfo(song_picks_paths[0])
               and ar in mediainfo(song_picks_paths[0])[t]):
                artist_name = mediainfo(song_picks_paths[0]).get(t, None)[ar]
                break
        for al in ['ALBUM', 'album', 'Album']:
            if (t in mediainfo(song_picks_paths[0])
               and al in mediainfo(song_picks_paths[0])[t]):
                album_name = mediainfo(song_picks_paths[0]).get(t, None)[al]

    if dir_prompts:
        print("\n\n--- Destination folder name ---\n")
        if artist_name:
            print(f"Proposed artist folder name: " + f"{artist_name}")
            print("Type [y] to confirm or enter the desired artist name "
                  + "instead")
        else:
            print("No artist name found. Please enter the desired name.")
        while True:
            artist_name_answer = input(":")
            if artist_name and artist_name_answer.lower() == "y":
                dst_album_path = dst_albums_dir / f"{artist_name}"
                break
            elif artist_name_answer.strip():
                dst_album_path = dst_albums_dir / artist_name_answer
                break
    elif not dir_prompts and artist_name:
        dst_album_path = dst_albums_dir / f"{artist_name}"
    elif not dir_prompts and not artist_name:
        while True:
            print("No artist name found. Please enter the desired name.")
            artist_name_answer = input(":")
            if artist_name_answer:
                break
        dst_album_path = dst_albums_dir / f"{artist_name_answer}"

    if dir_prompts:
        if album_name:
            print(f"\nProposed album folder name: " + f"{album_name}")
            print("Type [y] to confirm or enter the desired album name "
                  + "instead")
        else:
            print("No album name found. Please enter the desired name.")
        while True:
            album_name_answer = input(":")
            if album_name and album_name_answer.lower() == "y":
                dst_album_path = dst_album_path / f"{album_name}"
                break
            elif album_name_answer.strip():
                dst_album_path = dst_album_path / album_name_answer
                break
    elif not dir_prompts and album_name:
        dst_album_path = dst_album_path / f"{album_name}"
    elif not dir_prompts and not artist_name:
        while True:
            print("No album name found. Please enter the desired name.")
            album_name_answer = input(":")
            if album_name_answer:
                break
        dst_album_path = dst_albums_dir / f"{album_name_answer}"

    if dir_prompts:
        print(f"\nIf the destination {dst_album_path} needs another directory "
              + "(for example 'CD1' for multi-CD albums, type it in now. "
              + "Otherwise, leave blank.")
        add_dir_answer = input(":")
        if add_dir_answer == "":
            pass
        else:
            dst_album_path = dst_album_path / add_dir_answer

    return artist_name, album_name, dst_album_path


def get_cover_art(cfg) -> None:
    '''Fetches all images with proper suffixes found in the flac_album_path.
       Offers options to choose a main cover art file (copied directly into the
       destination folder), copy additional cover art preserving the folder
       structure and preview files (using OpenCV) or download a main cover art
       file from covers.musichoarders.xyz. Checks for existing files
       before copying.'''

    all_images_paths = []
    for suffix in cfg["cover_art_suffixes"]:
        all_images_paths.extend(list(cfg["flac_album_path"].rglob(
                                     f"*.{suffix}")))

    print("\n\n--- Cover Art ---\n")
    if all_images_paths:
        for nr, (fpath, fname) in enumerate([(x, x.relative_to(
                                                    cfg["flac_album_path"]))
                                             for x in all_images_paths]):
            img = cv2.imread(str(fpath))
            h, w, _ = img.shape
            print(nr, ": ", fname, f" ({w}x{h})")
    else:
        print("No cover art found. Would you like to download cover art from",
              "covers.musichoarders.xyz?\n[y] / [n]")
        while True:
            answer = input(":")
            if answer.lower() == "y":
                download_cover_art(cfg["artist_name"], cfg["album_name"],
                                   cfg["dst_album_path"],
                                   cfg["default_cover_art_name"])
                return
            elif answer.lower() == "n":
                return

    help_ = ("\n<number> - pick cover art to be copied to the "
             + f"destination folder as \"{cfg['default_cover_art_name']}\"."
             + "\np<number> - preview the image \nc<number> - copy "
             + "an additional file directly without changing "
             + "its name\nd - download main cover art from "
             + "covers.musichoarders.xyz"
             + "\nq - finish copying cover art and proceed\n"
             + "h - see this prompt again\n")
    print(help_)

    while True:
        answer = input(":")
        if answer[0] == "p":
            img = cv2.imread(str(all_images_paths[int(answer[1:])]))
            cv2.namedWindow("cover")
            cv2.imshow("cover", img)
            # The loop breaks on a closed window as well as on any keypress
            while cv2.getWindowProperty("cover", cv2.WND_PROP_VISIBLE) >= 1:
                cv2.waitKey(100)
        elif answer[0] == "c":
            misc_src = all_images_paths[int(answer[1:])]
            misc_dest = (cfg["dst_album_path"]
                         / misc_src.relative_to(cfg["flac_album_path"]))

            if not misc_dest.exists():
                misc_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(misc_src, misc_dest)
                print("Misc cover art succesfully copied as "
                      + f"{misc_dest}\n")
            else:
                print("Misc cover art already copied, skipping...\n")
        elif answer.isnumeric():
            main_src = all_images_paths[int(answer)]
            main_dest = (cfg["dst_album_path"]
                         / (cfg["default_cover_art_name"]
                            + all_images_paths[int(answer)].suffix))

            if not main_dest.exists():
                cfg["dst_album_path"].mkdir(parents=True, exist_ok=True)
                shutil.copy2(main_src, main_dest)
                print("Main cover art succesfully copied as "
                      + f"{main_dest.stem}\n")
            else:
                print("Main cover art already copied, skipping...\n")
        elif answer[0] == "h":
            print()
            for nr, f in enumerate([x.name for x in all_images_paths]):
                print(nr, ": ", f)
            print(help_)
        elif answer[0] == "d":
            download_cover_art(cfg["artist_name"], cfg["album_name"],
                               cfg["dst_album_path"],
                               cfg["default_cover_art_name"])
            print(help_)
            # printing it once again since we're still at choosing the ca
            # and the user might not realise that with just a ":" at the
            # bottom of the terminal
        elif answer[0] == "q":
            break
    return


def download_cover_art(artist_name, album_name, dst_album_path,
                       default_cover_art_name) -> None:
    '''Prepares a query for covers.musichoaders.xyz by asking whether artist
       name should be used and using the album name provided earlier. Takes
       the link to the chosen cover art and downloads with a preffered main
       cover art filename.'''

    print("\n\n--- Searching and downloading cover art ---\n")
    print(f"Proposed artist name: " + f"{artist_name}")
    print("Type [y] to confirm or enter the desired artist name instead,",
          "leave blank to not search for a specific artist")
    artist_name_answer = input(':')
    if artist_name_answer.lower() == "y":
        artist = artist_name
    elif artist_name_answer == "":
        artist = None
    else:
        artist = artist_name_answer

    baseurl = "https://covers.musichoarders.xyz/"
    params = {}

    if artist is not None:
        params['artist'] = artist
    params['album'] = album_name

    url = baseurl + "?" + urlencode(params)
    webbrowser.open(url)

    print("\nChoose a cover art, click on it, then paste its link here")
    while True:
        cover_art_link = input(':')
        if cover_art_link:
            break
    dst_album_path.mkdir(parents=True, exist_ok=True)
    covert_art_file = (dst_album_path / (default_cover_art_name
                       + cover_art_link[cover_art_link.rfind("."):]))
    with urlopen(cover_art_link) as resp, open(covert_art_file, "wb+") as f:
        shutil.copyfileobj(resp, f)

    print(f"\nSuccesfully downloaded {covert_art_file.name}")


def convert_songs(album) -> None:
    '''Converts all flac files into dst_format preserving subdirs. Checks if
       songs already exist. Makes subdirs if they don't exist.'''

    for song_flac in album.picks_paths:
        if (str(album.dst_path.name)
                == str(song_flac.parent.relative_to(album.flac_path))):
            dst_song_path = (album.dst_path
                             / (song_flac.stem + "." + album.dst_format))
        else:
            dst_song_path = (album.dst_path
                             / song_flac.parent.relative_to(album.flac_path)
                             / (song_flac.stem + "." + album.dst_format))
        print()
        if not dst_song_path.exists():
            print("Processing \"" + song_flac.name + "\"...", end='')
            sys.stdout.flush()
            seg = AudioSegment.from_file(song_flac)
            if not dst_song_path.parent.exists():
                dst_song_path.parent.mkdir(parents=True, exist_ok=True)
            tags_ = mediainfo(song_flac).get('TAG', {})
            if album.is_compilation:
                tags_['compilation'] = '1'
            seg.export(dst_song_path, format=album.dst_format,
                       parameters=album.ffmpeg_params.split(),
                       tags=tags_)
            print("DONE")
        else:
            print(f"\n{dst_song_path.stem} already exists, skipping...")
    print("\nAll conversions done.")
    return


if __name__ == "__main__":
    main()
