TABLE_COLUMNS = {

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

    'author': {
        'table': 'author',
        'author_id': 'author_id',
        'career_factor': 'career_compensation',
        'modified_hm_index': 'modified_hm_index',
    },

    'author_paper_field_effective_citation': {
        'table': 'author_paper_field_effective_citation',
        'paper_id': 'pub_id',
        'capped_adjusted_citations': 'capped_adjusted_citation',
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