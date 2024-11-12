from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
import requests
from tasks import review_code
import os 

app = FastAPI()
logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


@app.get("/")
def root():
    return {"message": "hello world"}


@app.post("/pull_request")
async def pull_request(request: Request):
    if request.headers.get("Content-Type") != "application/json":
        raise HTTPException(
            status_code=415, detail="Unsupported Media Type. Expected application/json"
        )

    data = await request.json()
    github_event = request.headers.get("X-Github-Event")

    if github_event == "pull_request":
        action = data["action"]
        repo = data["repository"]["full_name"]  # Get repo in 'owner/repo' format
        if action in {"opened", "synchronize"}:
            pr_number = data["number"]
            author = data["pull_request"]["user"]["login"]
            from_branch = data["pull_request"]["head"]["ref"]
            to_branch = data["pull_request"]["base"]["ref"]
            timestamp = data["pull_request"]["updated_at"]
            request_id = data["pull_request"]["id"]
            base = data["pull_request"]["base"]["sha"]
            head = data["pull_request"]["head"]["sha"]
            compare_url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            }
            response = requests.get(compare_url, headers=headers)

            if response.status_code == 200:
                # Extract the diff for each file
                comparison_data = response.json()
                diffs = []
                for file in comparison_data.get("files", []):
                    if "patch" in file:
                        diffs.append(file["patch"])  # Collect each file's patch (diff)

                        # Send diffs to the Celery task
                context = "\n".join(diffs)
                answer = review_code.delay(
                    context
                )  # Call the Celery task asynchronousl
                # Print only the diff information
                for diff in diffs:
                    print(diff)  # or use logger to capture this output in logs

                # Return a response with just the diffs if needed
                return JSONResponse(
                    content={"diffs": diffs, "answer": answer}, status_code=200
                )
            else:
                return JSONResponse(
                    content={"message": "Failed to fetch comparison"}, status_code=500
                )

        elif action == "closed":
            pull_request = data["pull_request"]
            if pull_request["merged"]:
                pr_number = data["number"]
                author = pull_request["user"]["login"]
                from_branch = pull_request["head"]["ref"]
                to_branch = pull_request["base"]["ref"]
                timestamp = pull_request["merged_at"]
                request_id = pull_request["id"]
                logger.info(
                    f"{author} merged branch {from_branch} to {to_branch} on {timestamp}"
                )
                return JSONResponse(
                    content={"message": "Merge processed"}, status_code=200
                )

    return JSONResponse(content={"message": "Unsupported event"}, status_code=200)
