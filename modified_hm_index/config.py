TABLE_COLUMNS = {

    # -----------------------------------------------------------
    # NOTE: this table is unique at (pub_id, author_id, field_name)
    # -- NOT at pub_id alone. It already contains the fully
    # combined per-author-per-field weight (author_field_weight,
    # i.e. Eq. 1/3/4/5's W_p^{f,i}) and the correct per-row
    # career_factor. calculator.py reads these directly rather
    # than recomputing them from author_contribution_weight.
    # -----------------------------------------------------------
    'author_paper_field_effective_citation': {
        'table': 'author_paper_field_effective_citation',
        'paper_id': 'pub_id',
        'author_id': 'author_id',
        'field_id': 'field_name',
        'career_factor': 'career_factor',
        'author_field_weight': 'author_field_weight',
        'capped_adjusted_citations': 'capped_adjusted_citation',
        'calculation_status': 'calculation_status',
    },

    'author': {
        'table': 'author',
        'author_id': 'author_id',
        'career_factor': 'career_compensation',
        'modified_hm_index': 'modified_hm_index',
    },

    'field_classification': {
        'table': 'field_classification',
        'paper_id': 'pub_id',

        'field_id_columns': [
            'field1_name',
            'field2_name',
            'field3_name',
        ],

        'field_weight_columns': [
            'field1_weight',
            'field2_weight',
            'field3_weight',
        ],
    },

    # -----------------------------------------------------------
    # NOTE: no longer used by the Modified Hm-index calculation --
    # author_field_weight in author_paper_field_effective_citation
    # already contains this table's contribution_weight fully
    # combined with the paper's field share. Kept here only in
    # case some other part of the system still reads this table
    # directly.
    # -----------------------------------------------------------
    'author_contribution_weight': {
        'table': 'author_contribution_weight',
        'paper_id': 'pub_id',

        'author_id_columns': [
            'author1id',
            'author2id',
            'author3id',
            'author4id',
            'author5id',
            'author6id',
            'author7id',
            'author8id',
            'author9id',
            'author10id',
        ],

        'contribution_weight_columns': [
            'author1id_weight',
            'author2id_weight',
            'author3id_weight',
            'author4id_weight',
            'author5id_weight',
            'author6id_weight',
            'author7id_weight',
            'author8id_weight',
            'author9id_weight',
            'author10id_weight',
        ],
    },
}
