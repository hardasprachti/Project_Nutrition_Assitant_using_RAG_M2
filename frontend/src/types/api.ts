// Mirrors the backend Pydantic schemas. Replaced by types generated from the
// OpenAPI spec in Phase 6; hand-written for the endpoints that exist so far.

export interface HealthResponse {
  status: "ok" | "unhealthy";
  database: "ok" | "unreachable";
  vector_extension: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
  };
}
