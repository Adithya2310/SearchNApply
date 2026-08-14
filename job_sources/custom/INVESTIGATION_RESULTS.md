# Custom-Scrape Integration Investigation Results

Date: 2024-08-14

## Summary

| Company    | ATS Platform             | API Found | Status              |
|------------|--------------------------|-----------|---------------------|
| AMD        | iCIMS (Jibe frontend)    | ✅ Yes    | Implemented         |
| Oracle     | Oracle Fusion Recruiting | ✅ Yes    | Implemented         |
| FM Global  | iCIMS (Jibe frontend)    | ✅ Yes    | Implemented         |
| Google     | Proprietary (in-house)   | ❌ No     | Not viable          |
| Microsoft  | Eightfold AI             | ✅ Sitemap | Implemented         |
| Qualcomm   | Eightfold AI             | ✅ Sitemap | Implemented         |

---

## Implemented Integrations

### AMD (`job_sources/custom/amd.py`)
- **API:** `GET https://careers.amd.com/api/jobs?limit=100&page=1`
- **Platform:** While AMD uses iCIMS as the underlying ATS, their branded
  frontend at careers.amd.com is powered by Jibe, which exposes a clean
  public JSON API.
- **Pattern:** Single-stage — full descriptions included in listing response.
- **Live verified:** 654+ jobs returned successfully.

### Oracle (`job_sources/custom/oracle.py`)
- **API (listings):** `GET /hcmRestApi/resources/latest/recruitingCEJobRequisitions?finder=findReqs;siteNumber=CX_45001`
- **API (details):** `GET /hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?finder=ById;Id="<id>",siteNumber="CX_45001"`
- **Platform:** Oracle Fusion Cloud Recruiting (Oracle's own product).
- **Pattern:** Two-stage — listing provides title/location/id, detail fetch
  needed for descriptions (split across ExternalDescriptionStr,
  ExternalQualificationsStr, ExternalResponsibilitiesStr).
- **Live verified:** Real postings returned (e.g. "Federal Project Manager II").

### FM Global (`job_sources/custom/fm_global.py`)
- **API:** `GET https://careers.fm.com/api/jobs?limit=100&page=1`
- **Platform:** Originally iCIMS (TalentBrew), now migrated to Jibe at
  careers.fm.com (old URL jobs-fmglobal.icims.com redirects).
- **Pattern:** Single-stage — full descriptions included in listing response.
- **Note:** Uses the same Jibe API pattern as AMD. A generic Jibe integration
  could potentially be extracted if more Jibe-powered sites are added.
- **Live verified:** Real postings returned (e.g. "Commercial Facilities Engineer").

### Microsoft (`job_sources/custom/microsoft.py`)
- **API:** No direct JSON API (Eightfold blocks unauthenticated requests).
- **Platform:** Eightfold AI (at apply.careers.microsoft.com).
- **Pattern:** Two-stage via Sitemap — `GET /careers/sitemap.xml?domain=microsoft.com` to get job URLs and basic titles from slugs, then `GET` individual job pages to extract full `JobPosting` data from embedded `application/ld+json`.
- **Live verified:** Over 2,000+ jobs found in sitemap.

### Qualcomm (`job_sources/custom/qualcomm.py`)
- **API:** No direct JSON API (Eightfold blocks unauthenticated requests).
- **Platform:** Eightfold AI (at careers.qualcomm.com).
- **Pattern:** Two-stage via Sitemap — identical to Microsoft, using `/careers/sitemap.xml?domain=qualcomm.com` and individual job page JSON-LD parsing.
- **Live verified:** Over 1,900+ jobs found in sitemap.

---

## Not Viable — No Usable API

### Google
- **Platform:** Proprietary in-house system built on Google's internal WIZ
  framework (HiringCportalFrontendUi).
- **Why not viable:** No public API. The frontend fetches data via internal
  endpoints (`/_/HiringCportalFrontendUi/...`) that return heavily obfuscated,
  batched Protocol Buffers over JSON. These endpoints are token-protected and
  impossible to cleanly reverse-engineer with standard HTTP requests.
- **Recommendation:** Keep inactive in the Watchlist.

---

## Patterns Discovered

### Jibe API (reusable)
AMD and FM Global both use the same Jibe platform with identical API
structures (`/api/jobs` returning paginated JSON with full descriptions).
If more Jibe-powered sites are added to the Watchlist, a generic
`job_sources/jibe.py` could be extracted similar to `job_sources/workday.py`.

### Eightfold AI (Sitemap + JSON-LD)
Both Microsoft and Qualcomm use Eightfold AI, which actively blocks
unauthenticated API access (`403 Forbidden` with `{"message": "Not authorized for PCSX"}`).
However, the platform exposes a complete sitemap (`/careers/sitemap.xml`) and
embeds `application/ld+json` (`JobPosting`) on every job page. This allows a robust
two-stage integration without needing a direct JSON API.
