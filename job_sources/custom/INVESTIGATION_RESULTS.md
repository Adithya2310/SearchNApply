# Custom-Scrape Integration Investigation Results

Date: 2024-08-14

## Summary

| Company    | ATS Platform             | API Found | Status              |
|------------|--------------------------|-----------|---------------------|
| AMD        | iCIMS (Jibe frontend)    | ✅ Yes    | Implemented         |
| Oracle     | Oracle Fusion Recruiting | ✅ Yes    | Implemented         |
| FM Global  | iCIMS (Jibe frontend)    | ✅ Yes    | Implemented         |
| Google     | Proprietary (in-house)   | ❌ No     | Not viable          |
| Microsoft  | Eightfold AI             | ❌ No     | Not viable          |
| Qualcomm   | Eightfold AI             | ❌ No     | Not viable          |

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

### Microsoft
- **Platform:** Recently migrated from a custom Adobe AEM frontend to
  Eightfold AI (at apply.careers.microsoft.com). The old gcsservices API
  no longer resolves.
- **Why not viable:** The Eightfold API endpoint
  (`/api/apply/v2/jobs?domain=microsoft.com`) returns `403 Forbidden`
  with `{"message": "Not authorized for PCSX"}`. Requires authenticated
  sessions and CSRF tokens that cannot be obtained via simple HTTP requests.
- **Recommendation:** Keep inactive in the Watchlist.

### Qualcomm
- **Platform:** Eightfold AI (same as Microsoft's new platform).
- **Why not viable:** Same Eightfold auth-blocking issue as Microsoft.
  The `/api/apply/v2/jobs?domain=qualcomm.com` endpoint returns
  `403 Forbidden` with the same "Not authorized for PCSX" message.
- **Recommendation:** Keep inactive in the Watchlist. If Eightfold's
  auth model changes in the future, both Microsoft and Qualcomm could
  become viable simultaneously.

---

## Patterns Discovered

### Jibe API (reusable)
AMD and FM Global both use the same Jibe platform with identical API
structures (`/api/jobs` returning paginated JSON with full descriptions).
If more Jibe-powered sites are added to the Watchlist, a generic
`job_sources/jibe.py` could be extracted similar to `job_sources/workday.py`.

### Eightfold AI (blocked)
Both Microsoft and Qualcomm use Eightfold AI, which actively blocks
unauthenticated API access. This is a platform-level limitation, not a
per-tenant configuration, so all Eightfold-powered sites are likely
non-viable for this integration pattern.
