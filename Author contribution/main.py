from database import get_connection
from author_contribution_calculator import AuthorContributionCalculator



def get_publications(offset=0, limit=204):

    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT 
            pub_id,
            author1id,
            author2id,
            author3id,
            author4id,
            author5id,
            author6id,
            author7id,
            author8id,
            author9id,
            author10id
        FROM public.author_contribution_weight
        ORDER BY pub_id ASC
        LIMIT %s OFFSET %s
    """

    cur.execute(query, (limit, offset))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows





def get_author_name(author_id):

    if author_id is None:
        return None


    conn = get_connection()
    cur = conn.cursor()


    query = """
        SELECT author_name
        FROM public.author
        WHERE author_id=%s
    """


    cur.execute(query, (author_id,))


    result = cur.fetchone()


    cur.close()
    conn.close()


    if result:
        return result[0]

    return None





def get_field_weights(pub_id):

    conn = get_connection()
    cur = conn.cursor()


    query = """
        SELECT

        field1_name,
        field1_weight,

        field2_name,
        field2_weight,

        field3_name,
        field3_weight

        FROM public.field_classification

        WHERE pub_id=%s
    """


    cur.execute(query, (pub_id,))


    row = cur.fetchone()


    cur.close()
    conn.close()



    fields = {}


    if row:


        if row[0] and row[1] is not None:

            fields[row[0]] = float(row[1])


        if row[2] and row[3] is not None:

            fields[row[2]] = float(row[3])


        if row[4] and row[5] is not None:

            fields[row[4]] = float(row[5])



    return fields






def update_author_weights(pub_id, result, author_ids):


    conn = get_connection()

    cur = conn.cursor()



    weights = []


    # Calculate weight for existing authors

    for author_id in author_ids:


        author_name = get_author_name(author_id)


        contribution = result["author_contributions"].get(
            author_name,
            0
        )


        weights.append(contribution)



    # Padding remaining author positions up to 10

    while len(weights) < 10:

        weights.append(None)




    query = """

    UPDATE public.author_contribution_weight

    SET

        author_ordering_norm=%s,

        author1id_weight=%s,
        author2id_weight=%s,
        author3id_weight=%s,
        author4id_weight=%s,
        author5id_weight=%s,
        author6id_weight=%s,
        author7id_weight=%s,
        author8id_weight=%s,
        author9id_weight=%s,
        author10id_weight=%s


    WHERE pub_id=%s

    """



    cur.execute(

        query,

        (

            result["ordering_norm"],

            weights[0],
            weights[1],
            weights[2],
            weights[3],
            weights[4],
            weights[5],
            weights[6],
            weights[7],
            weights[8],
            weights[9],

            pub_id

        )

    )



    conn.commit()


    cur.close()

    conn.close()







def process_publications(offset=0, limit=204):


    calculator = AuthorContributionCalculator()


    publications = get_publications(offset, limit)

    print(f"Processing {len(publications)} publications")
    print(f"Offset: {offset}, Limit: {limit}")



    for row in publications:



        pub_id = row[0]


        print("\n==============================")
        print("Processing:", pub_id)
        print("==============================")



        # Extract author IDs

        author_ids = list(row[1:])



        # Remove NULL author IDs

        author_ids = [

            author_id

            for author_id in author_ids

            if author_id is not None

        ]



        if len(author_ids) == 0:

            print("No authors found")

            continue



        # Get author names

        author_names = []



        for author_id in author_ids:


            name = get_author_name(author_id)


            if name:

                author_names.append(name)



        print("Authors:")
        for i,name in enumerate(author_names,1):

            print(i,name)




        # Get field weights

        fields = get_field_weights(pub_id)



        print("\nFields:")
        print(fields)



        if len(fields)==0:

            print("No field classification found")

            continue




        # Calculate contribution


        result = calculator.calculate_total_author_contributions(

            paper_id=pub_id,

            author_list=author_names,

            fields_data=fields

        )



        print("\nOrdering:", result["ordering_norm"])



        print("\nContribution:")

        for author,weight in result["author_contributions"].items():

            print(
                author,
                "=>",
                round(weight,6)
            )



        print(
            "Total:",
            result["total_weight"]
        )



        # Update database

        update_author_weights(

            pub_id,

            result,

            author_ids

        )



        print("\nUpdated successfully:", pub_id)









if __name__ == "__main__":

    import sys

    offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 204

    process_publications(offset, limit)


