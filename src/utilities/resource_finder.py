import urllib.parse


def get_learning_resources(skill):
    udemy_link = f"https://www.udemy.com/courses/search/?q={urllib.parse.quote(skill)}"
    youtube_link = f"https://www.youtube.com/results?search_query={urllib.parse.quote(skill + ' tutorial')}"
    coursera_link = f"https://www.coursera.org/search?query={urllib.parse.quote(skill)}"
    results = [
        {"title": f"{skill} - Udemy Courses", "link": udemy_link},
        {"title": f"{skill} - YouTube Tutorials", "link": youtube_link},
        {"title": f"{skill} - Coursera Courses", "link": coursera_link},
    ]
    return results

if __name__ == "__main__":
    skill_gap = "machine learning"
    resources = get_learning_resources(skill_gap)
    print("\nTop Learning Resources:\n")
    for i, res in enumerate(resources, 1):
        print(f"{i}. {res['title']}")
        print(res["link"])
        print()