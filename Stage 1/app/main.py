from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .routes import router

app = FastAPI(title="String Analyzer Service")
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	path = request.url.path
	is_post_strings = request.method == "POST" and path.endswith("/strings") and "/filter-by-natural-language" not in path
	is_get_with_query = request.method == "GET" and path.endswith("/strings")
	is_get_nl_filter = request.method == "GET" and path.endswith("/strings/filter-by-natural-language")

	if is_post_strings:
		errors = exc.errors()
		# Missing required field or invalid JSON -> 400, wrong type -> 422
		missing = any(
			(err.get("type") in {"missing", "field_required"}) or
			("field required" in str(err.get("msg", "")).lower())
			for err in errors
		)
		json_invalid = any(
			(err.get("type") in {"json_invalid", "value_error.jsondecode"}) or
			("json decode error" in str(err.get("msg", "")).lower())
			for err in errors
		)
		status = 400 if (missing or json_invalid) else 422
	elif is_get_with_query:
		status = 400
	elif is_get_nl_filter:
		# Missing required 'query' param should be 400 per spec intent
		status = 400
	else:
		status = 422
	return JSONResponse(status_code=status, content={"detail": exc.errors()})
