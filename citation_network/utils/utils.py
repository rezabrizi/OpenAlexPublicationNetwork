import urllib.parse
import requests
import logging
import time
import urllib

logger = logging.getLogger(__name__)


class _APIProfiler:
    def __init__(self):
        self.total_api_time = 0.0
        self.api_call_count = 0.0

    def reset(self):
        self.total_api_time = 0.0
        self.api_call_count = 0.0

    def track(self, start, end):
        self.total_api_time += start - end
        self.api_call_count += 1

    def get_summary(self):
        avg_time = (
            self.total_api_time / self.api_call_count if self.api_call_count > 0 else 0
        )
        return {
            "total_time": self.total_api_time,
            "api_calls": self.api_call_count,
            "average_time": avg_time,
        }


class _OAAPI:
    def __init__(self):
        self.session = requests.Session()
        self.profiler = _APIProfiler()

    def makeOAAPICall(
        self, entityType, parameters, session: requests.Session = None, rateInterval=0.0
    ):
        paramsEncoded = urllib.parse.urlencode(parameters)
        requestURL = f"https://api.openalex.org/{entityType}?{paramsEncoded}"
        logger.debug(f"Making API request: {requestURL}")

        if rateInterval > 0.0:
            logger.debug(f"Sleeping for {rateInterval} seconds before API call...")
            time.sleep(rateInterval)

        if session is None:
            session = requests.Session()

        try:
            start_time = time.time()
            response = session.get(requestURL).json()
            end_time = time.time()
            self.profiler.track(start_time, end_time)

            if "meta" not in response or "error" in response:
                if "error" in response and "message" in response:
                    errorMessage = f"{response["error"]} -- {response["message"]}"
                else:
                    errorMessage = f"Unknown Error\n Response: {response}"

                logger.error(f"OpenAlex API Error: {errorMessage}")
                raise Exception(
                    f'Error in OpenAlex API call for "{entityType}":\nInput: {parameters}\n\tURL: {requestURL}\n\tResponse: {errorMessage}'
                )
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Request failed: {e}")
            raise

    def makeOASingleWorksCall(self, workID, retries=3, backoff=2.0):
        """Calls OpenAlex API for a single work and handles errors gracefully."""
        requestURL = f"https://api.openalex.org/works/{workID}?mailto:reza.tabrizi.75024@gmail.com"
        logger.info(f"Making API request: {requestURL}")

        if self.session is None:
            self.session = requests.Session()  # Ensure session reuse

        for attempt in range(retries):
            try:
                start_time = time.time()
                response = self.session.get(requestURL)

                # Check HTTP status before calling .json()
                if response.status_code == 200:
                    end_time = time.time()
                    self.profiler.track(start_time, end_time)
                    try:
                        return response.json()
                    except requests.exceptions.JSONDecodeError:
                        logger.error(
                            f"Failed to decode JSON from OpenAlex API. Response: {response.text}"
                        )
                        return None  # Prevent crashing

                elif response.status_code == 429:  # Rate Limit Exceeded
                    logger.warning(f"Rate limit hit. Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff

                elif response.status_code >= 500:  # Server Errors
                    logger.error(f"Server error {response.status_code}. Retrying...")
                    time.sleep(backoff)

                else:  # Other errors (400, 403, etc.)
                    logger.error(
                        f"API request failed with status {response.status_code}: {response.text}"
                    )
                    return None  # Return None to prevent further failures

            except requests.exceptions.RequestException as e:
                logger.error(f"HTTP Request failed: {e}")
                time.sleep(backoff)

        logger.error(f"Max retries reached for {requestURL}. Skipping this work.")
        return None


def timeit(func):
    """Decorator to log execution time of functions."""

    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} executed in {end_time - start_time:.6f} seconds")
        return result

    return wrapper
