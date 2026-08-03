

# not sure this idea works
def get_listing(URL: str):
    """
    Given a URL to a job listing, find the relevant info,
    fill out the output .json file, and save it in 
    recruiter-agency/output/listings.
    """

    output = {
        'company': '',
        'position': '',
        'location': '',
        'salary': '',
        'start_date': '',
        'employment duration': '',
        'employment type': '',
        'post date':'',
        'description':'',
    }
    
    return output
