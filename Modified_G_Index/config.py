TABLE_COLUMNS = {

    # -----------------------------------------------------------
    # Same source table used by modified_hm_index. Unique at
    # (pub_id, author_id, field_name) -- already contains the
    # fully combined per-author-per-field weight
    # (author_field_weight, i.e. Eq. 1/3/4/5's W_p^{f,i}), the
    # correct per-row career_factor, and the Eq. 12 outlier-capped
    # citation (capped_adjusted_citation). calculator.py reads
    # these directly rather than recomputing them.
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
        'modified_g_index': 'modified_g_index',
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
}
