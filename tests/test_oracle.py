
from unittest.mock import patch, MagicMock
from job_sources.custom.oracle import fetch_jobs

class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception("HTTP Error")

def test_fetch_jobs_success():
    list_response_data = {
        "items": [{
            "requisitionList": [
                {
                    "Id": "1001",
                    "Title": "Software Engineer",
                    "PrimaryLocation": "Seattle, WA"
                },
                {
                    "Id": "1002",
                    "Title": "Product Manager",
                    "PrimaryLocation": "Austin, TX"
                }
            ]
        }]
    }

    detail_response_1001 = {
        "items": [{
            "ExternalDescriptionStr": "<p>Build cool things.</p>",
            "ExternalQualificationsStr": "<p>Know Python.</p>",
            "ExternalResponsibilitiesStr": "<p>Write code.</p>"
        }]
    }

    detail_response_1002 = {
        "items": [{
            "ExternalDescriptionStr": "Manage products.",
            "ExternalQualificationsStr": "",
            "ExternalResponsibilitiesStr": ""
        }]
    }

    def mock_get(url, **kwargs):
        if "recruitingCEJobRequisitions" in url:
            if "offset=0" in url:
                return FakeResponse(list_response_data)
            else:
                return FakeResponse({"items": []})
        elif "recruitingCEJobRequisitionDetails" in url:
            if "1001" in url:
                return FakeResponse(detail_response_1001)
            elif "1002" in url:
                return FakeResponse(detail_response_1002)
        return FakeResponse({}, 404)

    with patch('requests.get', side_effect=mock_get):
        jobs = fetch_jobs("oracle", company_name="Oracle", existing_job_ids=set())

    assert len(jobs) == 2
    
    # Check job 1
    job1 = next(j for j in jobs if j['title'] == 'Software Engineer')
    assert job1['company'] == 'Oracle'
    assert job1['source'] == 'custom_oracle'
    assert job1['location'] == 'Seattle, WA'
    assert '1001' in job1['url']
    # The strip_html function should remove tags
    assert "Build cool things." in job1['description_raw']
    assert "Know Python." in job1['description_raw']
    
    # Check job 2
    job2 = next(j for j in jobs if j['title'] == 'Product Manager')
    assert job2['description_raw'].strip() == "Manage products."

def test_fetch_jobs_skip_existing():
    list_response_data = {
        "items": [{
            "requisitionList": [
                {
                    "Id": "1001",
                    "Title": "Software Engineer",
                    "PrimaryLocation": "Seattle, WA"
                }
            ]
        }]
    }

    detail_called = False
    
    def mock_get(url, **kwargs):
        nonlocal detail_called
        if "recruitingCEJobRequisitions" in url:
            return FakeResponse(list_response_data)
        elif "recruitingCEJobRequisitionDetails" in url:
            detail_called = True
            return FakeResponse({})
        return FakeResponse({}, 404)

    # First we need to know the job ID that will be computed
    from job_sources.dedup import compute_job_id
    expected_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/1001"
    existing_id = compute_job_id("Oracle", "Software Engineer", expected_url)

    with patch('requests.get', side_effect=mock_get):
        jobs = fetch_jobs("oracle", company_name="Oracle", existing_job_ids={existing_id})

    assert len(jobs) == 0  # Known jobs are skipped entirely
    assert not detail_called

def test_fetch_jobs_dedup_within_run():
    # Return same job twice
    list_response_data = {
        "items": [{
            "requisitionList": [
                {
                    "Id": "1001",
                    "Title": "Software Engineer",
                    "PrimaryLocation": "Seattle, WA"
                },
                {
                    "Id": "1001",
                    "Title": "Software Engineer",
                    "PrimaryLocation": "Seattle, WA"
                }
            ]
        }]
    }

    def mock_get(url, **kwargs):
        if "recruitingCEJobRequisitions" in url:
            return FakeResponse(list_response_data)
        elif "recruitingCEJobRequisitionDetails" in url:
            return FakeResponse({"items": [{"ExternalDescriptionStr": "Details"}]})
        return FakeResponse({}, 404)

    with patch('requests.get', side_effect=mock_get):
        jobs = fetch_jobs("oracle", company_name="Oracle")

    # Should only return one instance
    assert len(jobs) == 1
