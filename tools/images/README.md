# Real profile images

`pipeline.py` turns the photo ZIP collected from Google Places into images the
site may publish, and **publishes nothing it cannot justify**. Raw photos, the
ZIP and every intermediate file stay in a work directory outside the
repository; the repository receives only the audit trail, the manifest and the
optimised files of approved images.

```sh
python3 -I tools/images/pipeline.py \
  --zip  /path/outside/repo/imagens.zip \
  --work /path/outside/repo/work \
  --sha256 4ae36b1b95a8deeb79afba26f94dd52d158831f94af5da7d951ba46817d55c77
python3 -I tools/apply_codemods.py c20_profile_images
./tools/run_all.sh
```

Every stage is checkpointed in `--work`; a re-run reuses the extraction, the
per-image analysis and every WebP already encoded.

## The four gates

| Gate | Decided by | Where it is recorded |
| --- | --- | --- |
| Profile identity: the Google place is this profile, not a namesake, a sibling branch, another franchise office or a development of the company | `pipeline.py` rules | `data/images_audit/perfis.csv` |
| Image identity: the photo was uploaded by the business itself | `pipeline.py` (author of the photo) | `inventario.csv`, `identidade_imagem` |
| Right of use | **a person**, with evidence | `data/image_rights.csv` |
| What the image shows (logo, facade, interior, team, institutional) | **a person** | `data/image_rights.csv`, `image_type` |

A photo being on Google is not a right of use: the Google Maps Platform terms
do not allow storing Places photos and republishing them outside the API. The
script never infers a right of use, and alt text is generated only from the
type a reviewer recorded, so nothing is described that nobody checked.

Profile identity rules, all deterministic:

* the distinctive words of the profile name (generic words such as
  *inmobiliaria*, *S.A.*, *sucursal* removed) must all be in the Google name;
* the Google address must contain the profile's city (with the spellings Google
  uses: *Cd. del Este*, *Cnel. Oviedo*, *Santaní*, *María Auxiliadora* …), or the
  Google website must be the profile's official domain;
* a branch whose Google address is in another city is rejected;
* a Google name that adds words of its own (*Buen Barrio Universitario - Crecer*,
  *Team Guilhem Costa RE/MAX Black*) stays pending, whatever the domain says: the
  domain proves the brand, not the unit;
* one Google place shared by several profiles goes to at most the one profile
  that passed every other check;
* anything else is pending, with the reason in `perfis.csv`.

## Approving an image

1. Pick a row of `data/images_audit/fila_revisao.csv` whose
   `identidade_imagem` is `confirmada`, and look at the photo in the work
   directory (`<work>/raw/<pasta>/<arquivo>`).
2. Obtain the basis of use from the business: written authorisation, or the
   business supplying the photo itself, or a licence.
3. Add a row to `data/image_rights.csv`:

   | column | value |
   | --- | --- |
   | `sha256` | from the queue |
   | `profile_id` | from the queue |
   | `image_type` | `logo`, `fachada`, `interior`, `equipe` or `institucional` |
   | `basis` | `autorizacao_escrita`, `foto_propria` or `licenca` |
   | `evidence` | where the proof is kept (e-mail, document, URL) |
   | `granted_by`, `granted_date` | who granted it, and when |
   | `reviewed_by`, `reviewed_date` | who checked the image and the proof |

4. Re-run the pipeline and the codemods. A row that fails any gate is refused
   and the reason is written to `inventario.csv` (`direitos_recusados`).

Removing a row and re-running withdraws the image: its files are deleted and
every page gets the generic identifier back, byte for byte.

## What ships

| File | Content |
| --- | --- |
| `site/assets/profiles/*.webp` | approved images only: 124/192 px for the card and profile slots, 480/960 px for the gallery |
| `data/profile_images.json` | manifest read by `tools/codemods/c20_profile_images.py` |
| `data/images_audit/` | `resumo.json`, `perfis.csv`, `inventario.csv`, `fila_revisao.csv` |

Names and profile links of third-party Google contributors are private people's
data and stay in the work directory (`detail.json`), never in the repository.

The `profile_images` check in `tools/audit.py` blocks a deploy if a published
image lacks a rights row, a file is missing, orphaned or over 200 KB, or any ZIP
or temporary file sits in `site/`.
