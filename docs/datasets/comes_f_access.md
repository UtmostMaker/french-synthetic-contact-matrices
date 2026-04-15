# COMES-F data access

## Primary source

- Study: Béraud et al. 2015, « The French Connection: The First Large Population-Based Contact Survey in France Relevant for the Spread of Infectious Diseases »
- Paper URL: https://doi.org/10.1371/journal.pone.0133203
- Project page: https://www.contactmatrix.fr/index.php/raw-data
- Raw-data DOI: https://doi.org/10.6084/m9.figshare.1466917
- Figshare landing page: https://figshare.com/articles/dataset/Data_file_for_Comes_F/1466917

## Public downloadable file

The public archive currently exposes one workbook:

- `RawData_ComesF.xlsx`
- Figshare file download URL: `https://ndownloader.figshare.com/files/2157552`
- License reported by Figshare API: `CC BY 4.0`

## Reproducible local download

From the repository root:

```bash
python scripts/download_comes_f.py
```

This writes:

- `data/raw/comes_f/RawData_ComesF.xlsx`
- `data/raw/comes_f/comes_f_figshare_metadata.json`

The script verifies the downloaded file against the MD5 checksum reported by Figshare.

## Important caveat for this project

The public workbook contains the listed diary contacts and coarse metadata for participants reporting many professional contacts. It does not expose those supplementary professional contacts in fully expanded person-level form. The current parser therefore reconstructs a transparent age-contact matrix from the explicitly listed contacts only, then optionally symmetrizes it for model benchmarking.

That means the project now uses a real public COMES-F benchmark, but not a perfect reproduction of the weighted matrices reported in the paper.
