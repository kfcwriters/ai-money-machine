def get_hasnode_publication_id():
    # The GQL API now accepts the host directly as the 'id' field in some mutations.
    # But we still need the actual ObjectId for the publishPost mutation.
    # We'll keep the fallback logic but add a cache file.
    cache_file = ".hasnode_pub_id"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return f.read().strip()
    query = """
    query($host: String!) {
      publication(host: $host) {
        id
      }
    }
    """
    variables = {"host": HASKNODE_PUBLICATION_HOST}
    headers = {"Authorization": HASKNODE_TOKEN, "Content-Type": "application/json"}
    resp = requests.post("https://gql.hashnode.com/", json={"query": query, "variables": variables}, headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        pub_id = data.get("data", {}).get("publication", {}).get("id")
        if pub_id:
            with open(cache_file, "w") as f:
                f.write(pub_id)
            logging.info(f"Resolved publication ID: {pub_id}")
            return pub_id
    logging.error("Could not fetch publication ID. Using host as fallback.")
    return HASKNODE_PUBLICATION_HOST

def publish_hashnode_article(ebook_title, problem_title, gumroad_url):
    publication_id = get_hasnode_publication_id()

    query = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post {
          id
          slug
          url
        }
      }
    }
    """
    blog_prompt = f"""Write a helpful 300‑word blog article about solving this problem: "{problem_title}". At the end, naturally recommend a $4.99 guide that solves it, with a link placeholder [GUIDE_LINK]. Use a friendly tone."""
    blog_body = llm_generate(blog_prompt)
    blog_body = blog_body.replace("[GUIDE_LINK]", gumroad_url)

    variables = {
        "input": {
            "title": f"How to {sanitize_text(ebook_title)}",
            "contentMarkdown": blog_body,
            "publicationId": publication_id,
            "tags": [],
            "disableComments": False
        }
    }
    headers = {
        "Authorization": HASKNODE_TOKEN,
        "Content-Type": "application/json"
    }
    response = requests.post(
        "https://gql.hashnode.com/",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30
    )
    logging.info(f"Hashnode status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            logging.error("Hashnode GraphQL errors: %s", json.dumps(data["errors"]))
        else:
            post_info = data.get("data", {}).get("publishPost", {}).get("post", {})
            slug = post_info.get("slug", "")
            url = post_info.get("url", "")
            if slug:
                logging.info(f"Hashnode post published: {slug}")
            if url:
                logging.info(f"Public URL: {url}")
    else:
        logging.error(f"Hashnode request failed: {response.text}")
