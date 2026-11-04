# Real profile images

`pipeline.py` turns the photo collection gathered from Google Maps (one folder
per profile, `info.json` + up to ten photos) into the images the site shows.
Raw photos, the ZIP and every intermediate file stay in a work directory
outside the repository; the repository receives the review decisions, the
manifest, the optimised files and the reports.

```sh
python3 -I tools/images/pipeline.py \
  --zip  /path/outside/repo/imagens.zip \
  --work /path/outside/repo/work \
  --sha256 4ae36b1b95a8deeb79afba26f94dd52d158831f94af5da7d951ba46817d55c77 \
  [--sheets]                       # contact sheets of candidates not yet reviewed
python3 -I tools/apply_codemods.py
./tools/run_all.sh
```

Every stage is checkpointed in `--work`: extraction, per-image analysis and
every WebP already encoded are reused on the next run.

## What decides publication

The blocking risk is a picture shown on the wrong business. An image ships
only when both of these hold:

| Gate | How | Recorded in |
| --- | --- | --- |
| **Profile identity**: the Google place is this profile, not a namesake, another branch, another franchise office, a development of the company or a business abroad | deterministic rules, then a human decision for every case they left pending | `reports/imagens-perfis.csv`, `data/images_review/identidade.csv` |
| **Content**: what the image shows | visual review on numbered contact sheets | `data/images_review/conteudo.csv` |

Content classes: `logo`, `fachada`, `interior`, `equipe`, `institucional`, or
`rejeitar:…` (photos of listed properties, lots and developments, other
businesses, unrelated or unusable pictures). Alt text is generated from the
class, so it never describes anything nobody looked at.

`aceito_principal` in `identidade.csv` marks moderate doubt: the profile gets
its single most reliable image and no gallery.

Identity rules, all deterministic:

* the distinctive words of the profile name (generic words such as
  *inmobiliaria*, *S.A.*, *sucursal* removed) must all be in the Google name;
* the Google address must contain the profile's city (with Google's spellings:
  *Cd. del Este*, *Cnel. Oviedo*, *Santaní*, *María Auxiliadora* …), or the Google
  website must be the profile's official domain;
* a branch whose Google address is in another city is rejected;
* a Google name that adds words of its own (*Buen Barrio Universitario -
  Crecer*) stays pending whatever the domain says: the domain proves the brand,
  not the unit;
* one Google place shared by several profiles goes to at most one of them,
  unless review shows the profiles are the same office listed twice.

Selection per profile: at most 5 images, at most 1 logo and 2 of each photo
class; near-duplicates (dHash ≤ 6) removed; a photo that also appears under
another unrelated profile is dropped (a shared brand logo is allowed).

## Files

| Variant | Size | Used for |
| --- | --- | --- |
| `…-124.webp`, `…-192.webp` | 124/192 px box | primary image in the 62 px card slot and 96 px profile slot (logos fitted, photos cropped square) |
| `…-g480.webp`, `…-g960.webp` | 480/960 px wide | profile gallery, `srcset` + `sizes`, lazy |

WebP, EXIF orientation applied, metadata dropped, transparency kept for logos;
quality is the highest that fits the budget (30/60 KB primary, 80/180 KB
gallery) and an image is shrunk slightly rather than shipped heavier. Small
originals are never enlarged.

Every page credits the source with a link to the business's Google Maps
listing. Names and profile links of third-party contributors stay in the work
directory, never in the repository.

## Outputs

| File | Content |
| --- | --- |
| `data/profile_images.json` | manifest read by `tools/codemods/c20_profile_images.py` |
| `site/assets/profiles/*.webp` | published files only |
| `reports/imagens-resumo.json` | totals |
| `reports/imagens-manifest.csv` | every published file with alt texts and origin |
| `reports/imagens-aprovadas.csv`, `-rejeitadas.csv`, `-pendentes.csv` | every source image with its decision and reason |
| `reports/imagens-perfis.csv` | all 500 profiles: identity decision, Google match, images published |

The `profile_images` check in `tools/audit.py` blocks a deploy if a published
image lacks a matching content review, a file is missing, orphaned or over
200 KB, a page shows images of a profile with none approved, or any archive or
temporary file sits in `site/`.

Withdrawing an image: change its row in `conteudo.csv` to `rejeitar:…` and
re-run; its files are deleted and the pages get the generic identifier back,
byte for byte.
