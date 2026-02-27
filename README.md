# CollectionBuilder-CSV

CollectionBuilder-CSV is a robust and flexible "stand alone" template for creating digital collection and exhibit websites using Jekyll and a metadata CSV.
Driven by your collection metadata, the template generates engaging visualizations to browse and explore your objects.
The resulting static site can be hosted on any basic web server (or built automatically using GitHub Actions).

Visit the [CollectionBuilder Docs](https://collectionbuilder.github.io/cb-docs/) for step-by-step details for getting started and building collections!

## Brief Overview of Building a Collection

The [CollectionBuilder Docs](https://collectionbuilder.github.io/cb-docs/) contain detailed information about building a collection from start to finish--including installing software, using Git/GitHub, preparing digital objects, and formatting metadata.
- Add your metadata as a CSV to your project repository's "_data" folder (see [upload metadata docs](https://collectionbuilder.github.io/cb-docs/docs/metadata/uploading/)).
- Edit your project's "_config.yml" with your collection information (see [site configuration docs](https://collectionbuilder.github.io/cb-docs/docs/config/)). Additional customization is done via a theme file, configuration files, CSS tweaks, and more--however, once your "_config.yml" is edited your site is ready to be previewed. 
- Generate your site using Jekyll! (see docs for how to [use Jekyll locally](https://collectionbuilder.github.io/cb-docs/docs/repository/generate/) and [deploy on the web](https://collectionbuilder.github.io/cb-docs/docs/deploy/))


----------

## Workflow

### Prerequisites

- Ruby + Bundler (`bundle install`)
- Python 3 + dependencies (`pip install pillow tqdm reverse_geocoder`)
- ImageMagick (used by the rake tasks via `mini_magick`)
- WSL with `lftp` installed (for deployment)
- A `deploy.env.ps1` file in the repo root (not committed) that sets `$RemoteHost`, `$RemoteUser`, and `$RemotePath`

### Configuration

All collection-specific settings live at the top of [utilities/generate_collection.py](utilities/generate_collection.py):

| Block | What it controls |
|---|---|
| `COLLECTION` | Slug (used for object IDs and CSV filenames), display name, default spotter |
| `ANNOTATION_FIELDS` | Maps output CSV column names to LabelMe JSON keys (e.g. `"species" → "flags"`) |
| `METADATA_DEFAULTS` | Static field values written to every row (`type`, `format`, `display_template`, etc.) |

The CollectionBuilder metadata pointer in [_config.yml](_config.yml) (`metadata:`) and the banner image in [_data/theme.yml](_data/theme.yml) (`featured-image:`) also need to stay in sync with the slug.

### 1. Add images

Add absolute paths to source images (one per line) in `_data/paw_sources.csv` under the `image_path` column.

### 2. Annotate species (optional)

```powershell
python utilities/setup_annotation.py
```

This copies each new source image into `annotation/` (preserving filenames, deduplicating if needed) and keeps `_data/annotation_map.csv` up to date. Open the `annotation/` folder in [LabelMe](https://github.com/labelmeai/labelme), set the species flags on each image, and save. The JSON sidecars are read automatically in the next step.

### 3. Generate the collection and deploy

```powershell
python utilities/generate_collection.py
```

This does everything in one shot:

1. Reads `_data/paw_sources.csv`, copies images to `objects/src/` as `paw_001.jpg`, `paw_002.jpg`, …
2. Extracts EXIF date/time/GPS and IPTC spotter from each image
3. Reverse-geocodes GPS coordinates to city + country (cached in `_data/geo_cache.json`)
4. Reads species flags from LabelMe annotation JSON sidecars
5. Writes `_data/paw-repository.csv` with all metadata
6. Runs `rake generate_derivatives` — converts source images to WebP at full, small (`800×800`), and thumb (`450×`) sizes
7. Runs `rake generate_banner` — crops the `featured-image` from `_data/theme.yml` to `assets/img/banner.webp`
8. Runs `deploy.ps1` — builds the Jekyll site and deploys via SFTP (lftp over WSL)

### Deploy only

To rebuild and redeploy without reprocessing images:

```powershell
bundle exec rake generate_banner   # optional, if banner changed
powershell -ExecutionPolicy Bypass -File deploy.ps1
```

`deploy.ps1` builds the Jekyll site with `JEKYLL_ENV=production` and mirrors `_site/` to the remote server via SFTP, skipping `.jpg` files (only WebP derivatives are served).

----------

## CollectionBuilder

<https://collectionbuilder.github.io/>

CollectionBuilder is a project of University of Idaho Library's [Digital Initiatives](https://www.lib.uidaho.edu/digital/) and the [Center for Digital Inquiry and Learning](https://cdil.lib.uidaho.edu) (CDIL) following the [Lib-Static](https://lib-static.github.io/) methodology. 
Powered by the open source static site generator [Jekyll](https://jekyllrb.com/) and a modern static web stack, it puts collection metadata to work building beautiful sites.

The basic theme is created using [Bootstrap](https://getbootstrap.com/).
Metadata visualizations are built using open source libraries such as [DataTables](https://datatables.net/), [Leafletjs](http://leafletjs.com/), [Spotlight gallery](https://github.com/nextapps-de/spotlight), [lazysizes](https://github.com/aFarkas/lazysizes), and [Lunr.js](https://lunrjs.com/).
Object metadata is exposed using [Schema.org](http://schema.org) and [Open Graph protocol](http://ogp.me/) standards.
