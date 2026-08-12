# import math
# from typing import List, Dict, Optional


# class AuthorContributionCalculator:
#     """
#     A class to calculate author contributions based on different ordering norms.
#     Supports Alphabetical/Random and Relative Contribution ordering.
#     """

#     def __init__(self):
#         self.field_weights = {}
#         self.author_positions = {}

#     def detect_ordering_norm(
#             self,
#             author_list: List[str],
#             paper_id: str
#     ) -> str:

#         sorted_authors = sorted(author_list)


#         if [a.lower() for a in author_list] == \
#            [a.lower() for a in sorted_authors]:

#             return "alphabetical"

#         else:

#             return "relative"


#     def calculate_alphabetical_weights(
#             self,
#             paper_id: str,
#             field_name: str,
#             field_weight: float,
#             num_authors: int
#     ) -> Dict[int,float]:


#         if num_authors == 0:
#             return {}


#         contribution = field_weight / num_authors


#         weights={}


#         for i in range(1,num_authors+1):

#             weights[i]=contribution


#         return weights



#     def calculate_relative_weights(
#             self,
#             paper_id: str,
#             field_name: str,
#             field_weight: float,
#             num_authors: int,
#             core_first_indices=None,
#             core_last_indices=None
#     ):


#         if num_authors==0:
#             return {}


#         core_first = core_first_indices or []
#         core_last = core_last_indices or []


#         eap_values={}


#         for idx in range(1,num_authors+1):

#             if idx in core_first:

#                 eap_values[idx]=sum(core_first)/len(core_first)


#             elif idx in core_last:

#                 eap_values[idx]=sum(core_last)/len(core_last)


#             else:

#                 eap_values[idx]=idx



#         harmonic_weights={}


#         for idx,eap in eap_values.items():

#             harmonic_weights[idx]=1/eap



#         total=sum(harmonic_weights.values())


#         weights={}


#         for idx,value in harmonic_weights.items():

#             weights[idx]=(field_weight*value)/total


#         return weights





#     def calculate_total_author_contributions(
#             self,
#             paper_id,
#             author_list,
#             fields_data,
#             core_first_indices=None,
#             core_last_indices=None
#     ):


#         num_authors=len(author_list)


#         ordering_norm=self.detect_ordering_norm(
#             author_list,
#             paper_id
#         )


#         author_contributions={

#             author:0.0

#             for author in author_list

#         }


#         detailed={}



#         for field,weight in fields_data.items():


#             if ordering_norm=="alphabetical":


#                 result=self.calculate_alphabetical_weights(

#                     paper_id,
#                     field,
#                     weight,
#                     num_authors

#                 )


#             else:


#                 result=self.calculate_relative_weights(

#                     paper_id,
#                     field,
#                     weight,
#                     num_authors,
#                     core_first_indices,
#                     core_last_indices

#                 )



#             detailed[field]={}



#             for index,value in result.items():

#                 author=author_list[index-1]


#                 detailed[field][author]=value


#                 author_contributions[author]+=value





#         return {


#             "ordering_norm":ordering_norm,

#             "field_weights":fields_data,

#             "author_contributions":author_contributions,

#             "detailed_contributions":detailed,

#             "total_weight":sum(
#                 author_contributions.values()
#             )

#         }









import math
from typing import List, Dict


class AuthorContributionCalculator:
    """
    Calculate author contributions assuming all papers follow
    relative contribution ordering.
    """

    def __init__(self):
        self.field_weights = {}
        self.author_positions = {}


    def calculate_relative_weights(
            self,
            paper_id: str,
            field_name: str,
            field_weight: float,
            num_authors: int,
            core_first_indices=None,
            core_last_indices=None
    ):

        if num_authors == 0:
            return {}


        core_first = core_first_indices or []
        core_last = core_last_indices or []


        eap_values = {}


        for idx in range(1, num_authors + 1):

            if idx in core_first:

                eap_values[idx] = (
                    sum(core_first) / len(core_first)
                )


            elif idx in core_last:

                eap_values[idx] = (
                    sum(core_last) / len(core_last)
                )


            else:

                eap_values[idx] = idx



        # Harmonic weighting
        harmonic_weights = {}

        for idx, eap in eap_values.items():

            harmonic_weights[idx] = 1 / eap



        total = sum(
            harmonic_weights.values()
        )


        weights = {}


        for idx, value in harmonic_weights.items():

            weights[idx] = (
                field_weight * value
            ) / total


        return weights



    def calculate_total_author_contributions(
            self,
            paper_id,
            author_list,
            fields_data,
            core_first_indices=None,
            core_last_indices=None
    ):


        num_authors = len(author_list)


        # Assume every paper follows relative ordering
        ordering_norm = "relative"



        author_contributions = {

            author: 0.0

            for author in author_list

        }


        detailed = {}



        for field, weight in fields_data.items():


            result = self.calculate_relative_weights(

                paper_id,

                field,

                weight,

                num_authors,

                core_first_indices,

                core_last_indices

            )


            detailed[field] = {}



            for index, value in result.items():


                author = author_list[index - 1]


                detailed[field][author] = value


                author_contributions[author] += value



        return {


            "ordering_norm": ordering_norm,


            "field_weights": fields_data,


            "author_contributions": author_contributions,


            "detailed_contributions": detailed,


            "total_weight": sum(
                author_contributions.values()
            )

        }