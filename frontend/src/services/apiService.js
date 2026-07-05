import axios from 'axios';

// Get scholar profile data
export const getScholarProfile = async () => {
  try {
    const response = await axios.get('/api/search', {
      params: {
        author: localStorage.getItem('searchedAuthor') || 'Patikiri Arachchige Don Shehan Nilmantha Wijesekara'
      }
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching scholar profile:', error);
    throw error;
  }
};

// Get publications data
export const getPublications = async (offset = 0, limit = 100) => {
  try {
    const response = await axios.get('/api/search', {
      params: {
        author: localStorage.getItem('searchedAuthor') || 'Patikiri Arachchige Don Shehan Nilmantha Wijesekara'
      }
    });
    
    // Return paginated publications
    const publications = response.data.publications || [];
    return publications.slice(offset, offset + limit);
  } catch (error) {
    console.error('Error fetching publications:', error);
    throw error;
  }
};

// Get dashboard data
export const getDashboard = async () => {
  try {
    const response = await axios.get('/api/search', {
      params: {
        author: localStorage.getItem('searchedAuthor') || 'Patikiri Arachchige Don Shehan Nilmantha Wijesekara'
      }
    });
    
    // Format dashboard data to match what DataExplorer expects
    return {
      total_publications: response.data.totalPublications || 0,
      total_citations: response.data.totalCitations || 0,
      i10_index: response.data.nmIndex || 0, // Note: In the code, nmIndex is used for i10_index
      h_index: response.data.hIndex || 0
    };
  } catch (error) {
    console.error('Error fetching dashboard data:', error);
    throw error;
  }
};