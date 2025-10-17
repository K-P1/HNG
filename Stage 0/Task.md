# Backend Wizards — Stage 0 Task: Build a Dynamic Profile Endpoint

Welcome to Stage 0:

In this task you'll build a simple RESTful API endpoint that returns your profile information along with a dynamic cat fact fetched from an external API. This validates your ability to consume third-party APIs, format JSON responses, and return dynamic data.

---

## Task — Profile Endpoint (core requirements)

### Required endpoint

- Create a GET endpoint at: `/me`
- The endpoint must return JSON data with `Content-Type: application/json`.
- Must integrate with the Cat Facts API to fetch dynamic cat facts.

### Response structure (required fields)

Your endpoint must return a JSON response in this exact format:

```json
{
  "status": "success",
  "user": {
    "email": "<your email>",
    "name": "<your full name>",
    "stack": "<your backend stack>"
  },
  "timestamp": "<current UTC time in ISO 8601 format>",
  "fact": "<random cat fact from Cat Facts API>"
}
```

#### Field specifications

- `status` — Must always be the string "success"
- `user.email` — Your personal email address
- `user.name` — Your full name
- `user.stack` — Your backend technology stack (e.g., "Node.js/Express", "Python/Django", "Go/Gin")
- `timestamp` — Current UTC time in ISO 8601 format (e.g., `2025-10-15T12:34:56.789Z`)
- `fact` — A random cat fact fetched from the Cat Facts API

---

## Implementation guidance

### Dynamic timestamp

- The `timestamp` must reflect the current UTC time at the moment of the request.
- Use ISO 8601 format for consistency.
- The `timestamp` should update with every new request.

### Cat Facts API integration

- Endpoint to use: `https://catfact.ninja/fact`
- Fetch a new cat fact on every request to `/me`.
- Handle potential API failures gracefully (consider what happens if the external API is down).
- Set appropriate timeout values for the external API call.

### Error handling

- If the Cat Facts API fails, consider returning a fallback message (for example, a short default fact) or an error response explaining the failure.
- Handle network errors and timeouts appropriately.
- Return appropriate HTTP status codes (e.g., `200 OK` on success, `502 Bad Gateway` if the external API failed and you choose to surface that as an error).

### Best practices

- Use environment variables for configuration where appropriate (e.g., port, timeouts).
- Include proper CORS headers if needed.
- Add basic logging for debugging.
- Consider rate limiting if deploying publicly.

---

## Acceptance criteria (checklist for grading / automated tests)

- [ ] A working `GET /me` endpoint is accessible and returns a `200 OK` status.
- [ ] Response structure strictly follows the defined JSON schema.
- [ ] All required fields (`status`, `user`, `timestamp`, `fact`) are present.
- [ ] `user` object contains `email`, `name`, and `stack` fields with valid string values.
- [ ] `timestamp` field returns the current UTC time in ISO 8601 format.
- [ ] `timestamp` updates dynamically with every new request.
- [ ] `fact` field contains a cat fact fetched from the Cat Facts API.
- [ ] A new cat fact is fetched on every request (not cached).
- [ ] Response `Content-Type` header is `application/json`.
- [ ] Code is well-structured and follows best practices for your chosen stack.

---

## Submission instructions

You can implement this in any language of your choice (e.g., Fortran, C, Assembly, etc.).

Host the API: Vercel is forbidden for this cohort. Do not use Render. Other hosting options such as Railway, Heroku, AWS, PXXL App, etc., are accepted.

Include the GitHub repo link with:

- Clear `README` with setup instructions
- Instructions to run locally
- List of dependencies and how to install them
- Environment variables needed (if any)
- Tests or API documentation (if any)

Test your endpoint before submission — ensure it returns the correct response format. Provide any relevant tests, API documentation, or notes in the repo.

You’re to create a rich post on LinkedIn, Dev.to, Hashnode, Medium, or X detailing your work processes, what this task taught you, and include supporting snapshots/images/videos.

### Submission: #IMPORTANT

For your submission, make use of the bot in the `#track-backend` Slack channel by entering `/stage-zero-backend` and submitting the requested URLs.

#### Submission Process :pushpin:

1. Verify your server works (test from multiple networks if possible).
2. Go to the `#track-backend` Slack channel.
3. Run the command: `/stage-zero-backend`
4. Submit the following:
   - Your server URL (e.g., `http://your-ip-address/me`)
   - Your GitHub repo link
   - Your full name
   - Your email
   - Stack
5. Check the Thanos bot for the error or success message after each attempt.

---

### Submission Deadline

Deadline: Sunday, 19 Oct 2025 GMT+1 (WAT)

---
