from decimal import Decimal

from psycopg2 import sql

from .models import (
    AuthorWeight,
    CitationPair,
    FieldData,
    ISCResult,
)


class ISCRepository:
    def __init__(
        self,
        connection,
    ):
        self.connection = connection

    def _table_columns(
        self,
        table_name: str,
    ) -> set[str]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                """,
                (table_name,),
            )

            return {
                row[0].lower()
                for row in cursor.fetchall()
            }

    def _resolve_citation_columns(
        self,
    ) -> tuple[str, str]:
        """
        Return:

            cited publication column,
            citing publication column.
        """

        columns = self._table_columns(
            "citation"
        )

        if {
            "cited_pub_id",
            "citing_pub_id",
        }.issubset(columns):
            return (
                "cited_pub_id",
                "citing_pub_id",
            )

        if {
            "pub_id",
            "cites_pub_id",
        }.issubset(columns):
            return (
                "pub_id",
                "cites_pub_id",
            )

        if {
            "pub_id",
            "cited_pub_id",
        }.issubset(columns):
            return (
                "cited_pub_id",
                "pub_id",
            )

        raise RuntimeError(
            "Unsupported public.citation structure."
        )

    def fetch_citation_pairs(
        self,
        limit: int | None = None,
    ) -> list[CitationPair]:
        (
            cited_column,
            citing_column,
        ) = self._resolve_citation_columns()

        query = sql.SQL(
            """
            SELECT DISTINCT
                {cited},
                {citing}
            FROM public.citation
            WHERE {cited} IS NOT NULL
              AND {citing} IS NOT NULL
              AND {cited} <> {citing}
            ORDER BY
                {cited},
                {citing}
            """
        ).format(
            cited=sql.Identifier(
                cited_column
            ),
            citing=sql.Identifier(
                citing_column
            ),
        )

        parameters: tuple = ()

        if limit is not None:
            query += sql.SQL(
                " LIMIT %s"
            )

            parameters = (
                limit,
            )

        with self.connection.cursor() as cursor:
            cursor.execute(
                query,
                parameters,
            )

            return [
                CitationPair(
                    cited_pub_id=row[0],
                    citing_pub_id=row[1],
                )
                for row in cursor.fetchall()
            ]

    def _available_author_slots(
        self,
    ) -> list[int]:
        columns = self._table_columns(
            "author_contribution_weight"
        )

        return [
            index
            for index in range(1, 11)
            if f"author{index}id" in columns
        ]

    def fetch_publication_author_weights(
        self,
        pub_id: str,
    ) -> list[AuthorWeight]:
        """
        Read real publication authors and their
        normalized overall contribution weights.

        Missing author weights are rejected.
        """

        columns = self._table_columns(
            "author_contribution_weight"
        )

        slots = (
            self._available_author_slots()
        )

        if not slots:
            raise RuntimeError(
                "No author ID columns were found in "
                "author_contribution_weight."
            )

        missing_weight_columns = [
            f"author{index}id_weight"
            for index in slots
            if (
                f"author{index}id_weight"
                not in columns
            )
        ]

        if missing_weight_columns:
            raise RuntimeError(
                "Missing author weight columns: "
                + ", ".join(
                    missing_weight_columns
                )
            )

        selected_columns = []

        for index in slots:
            selected_columns.extend(
                [
                    sql.Identifier(
                        f"author{index}id"
                    ),
                    sql.Identifier(
                        f"author{index}id_weight"
                    ),
                ]
            )

        query = sql.SQL(
            """
            SELECT {columns}
            FROM public.author_contribution_weight
            WHERE pub_id = %s
            """
        ).format(
            columns=sql.SQL(", ").join(
                selected_columns
            )
        )

        with self.connection.cursor() as cursor:
            cursor.execute(
                query,
                (pub_id,),
            )

            row = cursor.fetchone()

        if row is None:
            return []

        results: list[AuthorWeight] = []

        for offset in range(
            0,
            len(row),
            2,
        ):
            author_id = row[offset]
            weight = row[offset + 1]

            if author_id is None:
                continue

            author_id = author_id.strip()

            if not author_id:
                continue

            if weight is None:
                raise RuntimeError(
                    "Missing contribution weight "
                    f"for author {author_id} "
                    f"in publication {pub_id}."
                )

            results.append(
                AuthorWeight(
                    author_id=author_id,
                    weight=Decimal(
                        str(weight)
                    ),
                )
            )

        return results

    def fetch_publication_fields(
        self,
        pub_id: str,
    ) -> list[FieldData]:
        """
        Read fields belonging to the cited paper.

        These field weights are used to calculate
        the target author's raw field citation share.
        """

        required_columns = {
            "field1_name",
            "field1_weight",
            "field2_name",
            "field2_weight",
            "field3_name",
            "field3_weight",
        }

        columns = self._table_columns(
            "field_classification"
        )

        if not required_columns.issubset(
            columns
        ):
            missing = sorted(
                required_columns - columns
            )

            raise RuntimeError(
                "Missing field columns: "
                + ", ".join(missing)
            )

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    field1_name,
                    field1_weight,
                    field2_name,
                    field2_weight,
                    field3_name,
                    field3_weight
                FROM public.field_classification
                WHERE pub_id = %s
                """,
                (pub_id,),
            )

            row = cursor.fetchone()

        if row is None:
            return []

        fields_by_name: dict[
            str,
            Decimal,
        ] = {}

        for offset in range(
            0,
            6,
            2,
        ):
            field_name = row[offset]
            field_weight = row[offset + 1]

            if (
                not field_name
                or field_weight is None
            ):
                continue

            field_name = field_name.strip()

            if not field_name:
                continue

            decimal_weight = Decimal(
                str(field_weight)
            )

            if decimal_weight < 0:
                raise RuntimeError(
                    "Negative field weight for "
                    f"{field_name} in {pub_id}."
                )

            if decimal_weight == 0:
                continue

            fields_by_name[field_name] = (
                fields_by_name.get(
                    field_name,
                    Decimal("0"),
                )
                + decimal_weight
            )

        return [
            FieldData(
                field_name=name,
                field_weight=weight,
            )
            for name, weight
            in fields_by_name.items()
        ]

    def delete_results_for_pair(
        self,
        cited_pub_id: str,
        citing_pub_id: str,
    ) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM
                    public.influential_self_citations
                WHERE cited_pub_id = %s
                  AND citing_pub_id = %s
                """,
                (
                    cited_pub_id,
                    citing_pub_id,
                ),
            )

    def save_result(
        self,
        result: ISCResult,
    ) -> None:
        """
        Save Equation 7 and Equation 8 values.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO
                public.influential_self_citations (
                    cited_pub_id,
                    citing_pub_id,
                    target_author_id,

                    field_name,
                    field_weight,
                    target_author_overall_weight,

                    self_author_ids,
                    core_author_ids,
                    non_overlap_author_ids,

                    self_influence_sum,
                    core_influence_sum,
                    non_overlap_influence_sum,

                    core_author_count,
                    epsilon_zero,
                    epsilon_value,

                    isc_numerator,
                    isc_denominator,
                    isc_value,

                    raw_citation,
                    adjusted_citation,

                    calculated_at
                )
                VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (
                    cited_pub_id,
                    citing_pub_id,
                    target_author_id,
                    field_name
                )
                DO UPDATE SET
                    field_weight =
                        EXCLUDED.field_weight,

                    target_author_overall_weight =
                        EXCLUDED.target_author_overall_weight,

                    self_author_ids =
                        EXCLUDED.self_author_ids,

                    core_author_ids =
                        EXCLUDED.core_author_ids,

                    non_overlap_author_ids =
                        EXCLUDED.non_overlap_author_ids,

                    self_influence_sum =
                        EXCLUDED.self_influence_sum,

                    core_influence_sum =
                        EXCLUDED.core_influence_sum,

                    non_overlap_influence_sum =
                        EXCLUDED.non_overlap_influence_sum,

                    core_author_count =
                        EXCLUDED.core_author_count,

                    epsilon_zero =
                        EXCLUDED.epsilon_zero,

                    epsilon_value =
                        EXCLUDED.epsilon_value,

                    isc_numerator =
                        EXCLUDED.isc_numerator,

                    isc_denominator =
                        EXCLUDED.isc_denominator,

                    isc_value =
                        EXCLUDED.isc_value,

                    raw_citation =
                        EXCLUDED.raw_citation,

                    adjusted_citation =
                        EXCLUDED.adjusted_citation,

                    calculated_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    result.cited_pub_id,
                    result.citing_pub_id,
                    result.target_author_id,

                    result.field_name,
                    result.field_weight,
                    result.target_author_overall_weight,

                    result.self_author_ids,
                    result.core_author_ids,
                    result.non_overlap_author_ids,

                    result.self_influence_sum,
                    result.core_influence_sum,
                    result.non_overlap_influence_sum,

                    result.core_author_count,
                    result.epsilon_zero,
                    result.epsilon_value,

                    result.isc_numerator,
                    result.isc_denominator,
                    result.isc_value,

                    result.raw_citation,
                    result.adjusted_citation,
                ),
            )

    def refresh_equation_9_results(
        self,
    ) -> None:
        """
        Calculate Equation 9 using every stored
        Equation 8 row.

        TC_adjusted(p, i)
            =
        SUM over q and f of
        TC_adjusted(p, i, q, f)
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM
                public.author_paper_adjusted_citations;
                """
            )

            cursor.execute(
                """
                INSERT INTO
                public.author_paper_adjusted_citations (
                    cited_pub_id,
                    target_author_id,
                    citing_paper_count,
                    field_row_count,
                    total_raw_citation,
                    total_adjusted_citation,
                    calculated_at
                )
                SELECT
                    cited_pub_id,
                    target_author_id,

                    COUNT(
                        DISTINCT citing_pub_id
                    )::INTEGER,

                    COUNT(*)::INTEGER,

                    SUM(raw_citation),

                    SUM(adjusted_citation),

                    CURRENT_TIMESTAMP

                FROM
                    public.influential_self_citations

                GROUP BY
                    cited_pub_id,
                    target_author_id;
                """
            )