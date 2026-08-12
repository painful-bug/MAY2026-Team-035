from postgrest.exceptions import APIError

from app.repositories.worker_repository import _job_rows


def test_worker_job_read_retries_without_the_v2_column_on_legacy_view() -> None:
    selections: list[str] = []

    class Query:
        def __init__(self, columns: str) -> None:
            self.columns = columns

        def execute(self):
            if "is_forced" in self.columns:
                raise APIError(
                    {
                        "message": "column my_worker_job.is_forced does not exist",
                        "code": "42703",
                    }
                )
            return type(
                "Response", (), {"data": [{"assignment_id": "assignment-id"}]}
            )()

    def query(columns: str) -> Query:
        selections.append(columns)
        return Query(columns)

    assert _job_rows(query) == [{"assignment_id": "assignment-id", "is_forced": False}]
    assert "is_forced" in selections[0]
    assert "is_forced" not in selections[1]
