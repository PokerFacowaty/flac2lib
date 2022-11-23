flac2lib is a simple script I've made (and then expanded with like a milion random ideas) for myself for easier music library management, specifically batch converting flac files into mp3 with regard to my mp3 music library schema.
# Prerequisites
- [Python 3](https://www.python.org/downloads/)
- [Pydub](https://pydub.com/) (`pip install pydub`)
- [ffmpeg / libav (required by Pydub)](https://github.com/jiaaro/pydub#getting-ffmpeg-set-up)
- [PyYAML](https://pyyaml.org/) (`pip install PyYAML`)
- [opencv-python](https://pypi.org/project/opencv-python/) (`pip install opencv-python`)

# Installation

Download the files
- Clone the repo:
```
git clone https://github.com/PokerFacowaty/flac2lib
```
- ... or simply download `flac2lib.py` and `config.yaml` and store them in the same directory

# Configuration
## config.yaml
- Open `config.yaml`
- By default, the file will look like this:
```yaml
# Docs: https://github.com/PokerFacowaty/flac2lib
flac_albums_dir:
dst_albums_dir:
entire: False
num_albums_to_show: 10
dir_name_prompts: True
latest: False
get_cover_art: True
default_cover_art_name: cover # copied straight to the album folder
cover_art_suffixes: ['jpg', 'png', 'jpeg']
destination_format: mp3
ffmpeg_params: -q:a 2
# For the MP3 preset, use the "ffmpeg option" table in this article
# of the ffmpeg docs:
# https://trac.ffmpeg.org/wiki/Encode/MP3
# Use for other formats accordingly.
```
Explanations for all config entries:
- `flac_albums_dir:` - the directory that contains album folders with flac files
- `dst_albums_dir:` - the destination directory for converted files
- `entire:` - convert entire albums without asking for a list of songs to be converted; `False` by default
- `num_albums_to_show` - the amount of albums that should be listed when albums are presented to be chosen; `10` by default, ignored when `entire:` is set to `True` or the `-e / --entire` option is used
- `dir_name_prompts` - prompt about album/artist folder paths, uses ARTIST and ALBUM tags for dir and subdir without asking if `False`; `True` by default
- `latest` - pick the most recently modified flac folder; `False` by default
- `get_cover_art` - copy the cover art; `True` by default
- `default_cover_art_name` - the default name for the main cover art without its suffix; `cover` by default
- `cover_art_suffixes` - a list of accepted covert art suffixes; `['jpg', 'png', 'jpeg']` by default
- `destination_format` - the format that flacs will be converted to
- `ffmpeg_params` - additional ffmpeg parameters, the preset / bitrate for MP3 should be specified here; `-q:a 2` (VB2) by default

# Usage
To use flac2lib, simply start it when in the same directory:

```
python flac2lib.py
```
(or if you have Python 2 installed)
```
python3 flac2lib.py
```

## Arguments
- `-h, --help` - show help
- `-c, --config <file>` - use a custom config file
- `-e, --entire` - convert the entire directory
- `-s, --source <dir>` - specify the source album directory
- `-d, --destination <dir>` - specify the destination album directory
- `-l, --latest` - only convert the most recently modified folder in the flac albums directory
- `--skip-cover-art` - skip the process of copying covert art entirely
- `--skip-dir-prompts` - skip prompts about album/artist folder paths, use ARTIST and ALBUM tags for dir and subdir without asking
- `--compilation` - skip the prompt about whether a compilation tag should be added, mark the album as a compilation
- `--not-compilation` - see above


# Possible future improvements:
- [ ] Fixing case-sensitivity for retrieving artist and album names from tags
- [x] Showing covert art's size when listing
- [x] Fixing main cover art for multi-CD albums (is copied to the main directory and therefore usually not found by players which are looking inside the final (ex. `Disc 1` directory))
- [ ] Warning about potential non-allowed characters in filepaths (especially with Windows in mind)
- [x] An option to download cover art (MusicBrainz? covers.musichoarders.xyz?)
- [x] Marking the album as a compilation