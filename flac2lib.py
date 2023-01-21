from pydub import AudioSegment
from pydub.utils import mediainfo
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import getopt
import sys
import yaml
import cv2
import shutil
import webbrowser


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
    '''Parses the config file and initiates a loop of calling process_album()
       until the user decides they're done with choosing albums, then proceeds
       to convert all the albums in the queue.'''
    opts, args = getopt.getopt(sys.argv[1:], "hes:n:d:c:l",
                               ["help", "entire", "source=", "number=",
                                "destination=", "config=", "latest",
                                "skip-cover-art", "skip-dir-prompts",
                                "compilation", "not-compilation"])

    config_file = 'config.yaml'
    flac_album_path = None
    dst_album_path = None
    entire = None
    latest = None
    cover_art = None
    dir_prompts = None
    is_compilation = None

    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print("\n----- flac2lib by PokerFacowaty -----",
                  "\nPossible options:",
                  "\n[-h, --help] - open this prompt",
                  "\n[-c, --config] - point to a specific yaml config file",
                  "\n[-e, --entire] - convert an entire folder",
                  "\n[-s, --source] - provide the source album folder",
                  "\n[-d, --destination] - provide the destination folder",
                  "\n[-l, --latest] - convert the most recently modified",
                  "folder",
                  "\n[--skip-cover-art] - skip copying the cover art",
                  "\n[--skip-dir-prompts] - use ARTIST and ALBUM tags for",
                  "directory names without asking",
                  "\n[--compilation] - mark the album as compilation and skip",
                  "the question",
                  "\n[--not-compilation] - mark the album as not",
                  "a compilation and skip the question",
                  "\nDocs: https://github.com/PokerFacowaty/flac2lib\n")
            return
        elif opt in ["-c", "--config"]:
            config_file = arg
        elif opt in ["-e", "--entire"]:
            entire = True
        elif opt in ["-s", "--source"]:
            flac_album_path = Path(arg)
        elif opt in ["-d", "--destination"]:
            dst_album_path = Path(arg)
        elif opt in ["-l", "--latest"]:
            latest = True
        elif opt in ["--skip-cover-art"]:
            cover_art = False
        elif opt in ["--skip-dir-prompts"]:
            dir_prompts = False
        elif opt in ["--compilation"]:
            is_compilation = True
        elif opt in ["--not-compilation"]:
            is_compilation = False

    config = yaml.safe_load(open(config_file))
    flac_albums_dir = Path(config["flac_albums_dir"])
    dst_albums_dir = Path(config["dst_albums_dir"])
    if entire is None:
        entire = config["entire"]
    num_albums_to_show = config["num_albums_to_show"]
    if dir_prompts is None:
        dir_prompts = config["dir_name_prompts"]
    if latest is None:
        latest = config["latest"]
    if cover_art is None:
        cover_art = config["get_cover_art"]
    default_cover_art_name = config["default_cover_art_name"]
    cover_art_suffixes = config["cover_art_suffixes"]
    dst_format = config["destination_format"]
    ffmpeg_params = config["ffmpeg_params"]

    print("\n----- flac2lib.py by PokerFacowaty -----")
    print("https://github.com/PokerFacowaty/flac2lib")

    while process_album(flac_album_path, flac_albums_dir, num_albums_to_show,
                        latest, is_compilation, entire, dst_albums_dir,
                        dir_prompts, cover_art, dst_album_path,
                        default_cover_art_name, cover_art_suffixes,
                        ffmpeg_params, dst_format):
        continue

    for album in queue:
        convert_songs(album)


def process_album(flac_album_path, flac_albums_dir, num_albums_to_show, latest,
                  is_compilation, entire, dst_albums_dir, dir_prompts,
                  cover_art, dst_album_path, default_cover_art_name,
                  cover_art_suffixes, ffmpeg_params, dst_format):
    '''Gets all the info that is needed about the album and stores it in an
       AlbumToProcess object inside the queue list.'''

    if flac_album_path is None:
        flac_album_path = get_flac_album_path(flac_albums_dir,
                                              num_albums_to_show, latest)

    if is_compilation is None:
        is_compilation = ask_if_compilation()

    song_picks_paths = pick_songs(flac_album_path, entire)

    if dst_album_path is None:
        artist_name, album_name, dst_album_path = get_dst_album_path(
                                                    song_picks_paths,
                                                    dst_albums_dir,
                                                    dir_prompts)

    if cover_art:
        get_cover_art(flac_album_path, artist_name, album_name,
                      dst_album_path, default_cover_art_name,
                      cover_art_suffixes)

    queue.append(AlbumToProcess(dst_album_path, song_picks_paths,
                                flac_album_path, ffmpeg_params, dst_format,
                                is_compilation))

    answer = input("\nWould you like to add process more albums? [y/n]\n")
    if answer.lower() == "y":
        return True
    else:
        return False


def get_flac_album_path(flac_albums_dir, num_albums_to_show, latest):
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

    answer = input("\nChoose the album\n:")
    return folder_paths_to_show[int(answer)]


def ask_if_compilation():
    print("\n\n--- Compilation ---\n")
    print("Is the album a compilation? (adds compilation = 1 to the tags)")
    print("[y] / [n]")
    while True:
        answer = input(':')
        if answer.lower() == "y":
            return True
        elif answer.lower() == "n":
            return False


def pick_songs(flac_album_path, entire):
    '''Fetches all the flac files found in the album path, takes user input
       on which ones should be chosen and returns the paths for those. Returns
       all paths found if 'entire' is set to True.'''

    all_flac_files_paths = list(flac_album_path.rglob("*.flac"))

    if not entire:
        print("\n\n--- Songs ---\n")
        for nr, f in enumerate(sorted([x.name for x in all_flac_files_paths])):
            print(nr, ": ", f)
        print()

        answer = input("Choose songs, comma separated\n:")
        song_picks = [int(x) for x in str(answer).split(',')]
    elif entire:
        song_picks = list(range(len(all_flac_files_paths)))
    return [all_flac_files_paths[x] for x in song_picks]


def get_dst_album_path(song_picks_paths, dst_albums_dir, dir_prompts):
    '''Proposes an artist/album combo for the destination dir and subdir names
       based on the flac's metadata. Takes confirmation or custom names as
       input. Asks if there is an additional folder needed (such as 'CD1' for
       multi-CD albums), since doing so automatically would be overly complex
       and only cover some cases. The asking proccess is obviously skipped
       if the --skip-dir-prompts argument is used. Constructs and returns
       a full destination folder path.'''

    if ('TAG' in mediainfo(song_picks_paths[0])
       and 'ARTIST' in mediainfo(song_picks_paths[0])['TAG']):
        artist_name = mediainfo(song_picks_paths[0]).get('TAG', None)['ARTIST']
    elif ('TAG' in mediainfo(song_picks_paths[0])
          and 'artist' in mediainfo(song_picks_paths[0])['TAG']):
        artist_name = mediainfo(song_picks_paths[0]).get('TAG', None)['artist']
    else:
        artist_name = None

    if ('TAG' in mediainfo(song_picks_paths[0])
       and 'ALBUM' in mediainfo(song_picks_paths[0])['TAG']):
        album_name = mediainfo(song_picks_paths[0]).get('TAG', None)['ALBUM']
    elif ('TAG' in mediainfo(song_picks_paths[0])
          and 'album' in mediainfo(song_picks_paths[0])['TAG']):
        album_name = mediainfo(song_picks_paths[0]).get('TAG', None)['album']
    else:
        album_name = None

    if dir_prompts:
        print("\n\n--- Destination folder name ---\n")
        if artist_name:
            print(f"Proposed artist folder name: " + f"{artist_name}")
            print("Type \"y\" to confirm or enter the desired artist name "
                  + "instead")
        else:
            print("No artist name found. Please enter the desired name.")
        artist_name_answer = input(":")
        if artist_name and artist_name_answer.lower() == "y":
            dst_album_path = dst_albums_dir / f"{artist_name}"
        else:
            dst_album_path = dst_albums_dir / artist_name_answer
    elif not dir_prompts and artist_name:
        dst_album_path = dst_albums_dir / f"{artist_name}"
    elif not dir_prompts and not artist_name:
        print("No artist name found. Please enter the desired name.")
        artist_name_answer = input(":")
        dst_album_path = dst_albums_dir / f"{artist_name_answer}"

    if dir_prompts:
        if album_name:
            print(f"\nProposed album folder name: " + f"{album_name}")
            print("Type \"y\" to confirm or enter the desired album name "
                  + "instead")
        else:
            print("No album name found. Please enter the desired name.")
        album_name_answer = input(":")
        if album_name and album_name_answer.lower() == "y":
            dst_album_path = dst_album_path / f"{album_name}"
        else:
            dst_album_path = dst_album_path / album_name_answer
    elif not dir_prompts and album_name:
        dst_album_path = dst_album_path / f"{album_name}"
    elif not dir_prompts and not artist_name:
        print("No album name found. Please enter the desired name.")
        album_name_answer = input(":")
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


def get_cover_art(flac_album_path, artist_name, album_name, dst_album_path,
                  default_cover_art_name, cover_art_suffixes):
    '''Fetches all images with proper suffixes found in the flac_album_path.
       Offers options to choose a main cover art file (copied directly into the
       destination folder), copy additional cover art preserving the folder
       structure and preview files (using OpenCV) or download a main cover art
       file from covers.musichoarders.xyz. Checks for existing files
       before copying.'''

    all_images_paths = []
    for suffix in cover_art_suffixes:
        all_images_paths.extend(list(flac_album_path.rglob(f"*.{suffix}")))

    print("\n\n--- Cover Art ---\n")
    if all_images_paths:
        for nr, (fpath, fname) in enumerate([(x, x.relative_to(
                                                    flac_album_path))
                                             for x in all_images_paths]):
            img = cv2.imread(str(fpath))
            h, w, _ = img.shape
            print(nr, ": ", fname, f" ({w}x{h})")
    else:
        print("No cover art found. Would you like to download cover art from",
              "covers.musichoarders.xyz?\n[y] / [n]")
        answer = input(":")
        if answer.lower() == "y":
            download_cover_art(artist_name, album_name, dst_album_path,
                               default_cover_art_name)
            return
        elif answer.lower() == "n":
            return

    help_ = ("\n<number> - pick cover art to be copied to the"
             + f"destination folder as \"{default_cover_art_name}\"."
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
            misc_dest = (dst_album_path
                         / misc_src.relative_to(flac_album_path))

            if not misc_dest.exists():
                misc_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(misc_src, misc_dest)
                print("Misc cover art succesfully copied as " + f"{misc_dest}")
            else:
                print("Misc cover art already copied, skipping...")
        elif answer.isnumeric():
            main_src = all_images_paths[int(answer)]
            main_dest = (dst_album_path
                         / (default_cover_art_name
                            + all_images_paths[int(answer)].suffix))

            if not main_dest.exists():
                dst_album_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(main_src, main_dest)
                print("Main cover art succesfully copied as "
                      + f"{main_dest.stem}")
            else:
                print("Main cover art already copied, skipping...")
        elif answer[0] == "h":
            print()
            for nr, f in enumerate([x.name for x in all_images_paths]):
                print(nr, ": ", f)
            print(help_)
        elif answer[0] == "d":
            download_cover_art(artist_name, album_name, dst_album_path,
                               default_cover_art_name)
            print(help_)
            # printing it once again since we're still at choosing the ca
            # and the user might not realise that with just a ":" at the
            # bottom of the terminal
        elif answer[0] == "q":
            break
    return


def download_cover_art(artist_name, album_name, dst_album_path,
                       default_cover_art_name):
    '''Prepares a query for covers.musichoaders.xyz by asking whether artist
       name should be used and using the album name provided earlier. Takes
       the link to the chosen cover art and downloads with a preffered main
       cover art filename.'''
    print("\n\n--- Searching and downloading cover art ---\n")
    print(f"Proposed artist name: " + f"{artist_name}")
    print("Type \"y\" to confirm or enter the desired artist name instead,",
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
    cover_art_link = input(':')
    dst_album_path.mkdir(parents=True, exist_ok=True)
    covert_art_file = (dst_album_path / (default_cover_art_name
                       + cover_art_link[cover_art_link.rfind("."):]))
    with urlopen(cover_art_link) as resp, open(covert_art_file, "wb+") as f:
        shutil.copyfileobj(resp, f)

    print(f"\nSuccesfully downloaded {covert_art_file.name}")


def convert_songs(album):
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
