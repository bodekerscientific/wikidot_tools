# Program to download an entire wiki (except for history) from Wikidot and then to keep it synchronized.
# The wiki is downloaded to a directory.  Each wiki page generates two files and possibly a directory:
#     <page>.txt containing the source of the page
#     <page>.xml containing the metadata of the page
#     <page> a directory containing the attached files (created only if there are attached files)

# The basic scheme is to create a list of all pages in the wiki sorted from most-recently-updated to least-recently-updated.
# The downloader then walks the list, downloading new copies of each page which is newer on the wiki than in the local copy.
#    It stops when it finds a page where the local copy is up-to-date
#          (Note that this leave it vulnerable to a case where the downloader fails partway through and updates some pages and not others.
#          The next time it is run, if any pages have been updated in the mean time, the massed pages won;t be noticed.
#          Since the alternative is to check every page every time, and since this was written to deal with a wiki with >20K pages, it is an accepted issue to be dea;lt with by hand.)
#    The next step is to compare the list of all local .txt files with the list of all pages, and to download any which are missing.
#          (Note that this does not deal with deleted .xml files or deleted attached files.  This fairly cheap to check, so it might be a useful enhancement.)
#    The final step is to look for local .txt files which are not on the wiki.  These will typically be files which have been deleted on the wiki.  They are deleted locally.

# The wiki to be synched and the credentials are stoed in a file url.txt.  It contains a single line of text of the form:
#      https://fancyclopedia:rdS...80g@www.wikidot.com/xml-rpc-api.php
# where 'fancyclopedia' is the wiki and 'rdS...80g' is the access key

# The synched wiki will be put into a directory 'site' one level up from the Python code.

# It was developed in PyCharm2016


from pathlib import Path
from typing import Iterable, List
from xmlrpc import client
import xml.etree.ElementTree as ET
import os
import datetime
import base64
import fire
import requests

def DecodeDatetime(dtstring):
    if dtstring == None:
        return datetime.datetime(1950, 1, 1, 1, 1, 1)    # If there's no datetime, return something early
    if not dtstring.endswith("+00:00"):
        raise ValueError("Could not decode datetime: '")+dtstring+"'"
    return datetime.datetime.strptime(dtstring[:-6], '%Y-%m-%dT%H:%M:%S')

# Download a page from Wikidot.
# The page's contents are stored in their files, the source in <saveName>.txt, the HTML in <saveName>..html, and all of the page information in <saveName>.xml
# The return value is True when the Wikidot version of the page is newer than the local version, and False otherwise
def DownloadPage(localName, site_name, url):

    # Download the page's data
    print("   Downloading: '" + localName + "'")
    wikiName=localName.replace("_", ":", 1)  # Convert back to the ":" form for downloading)
    if wikiName == "con-": # "con" is a special case since that is a reserved word in Windoes and may not be used as a filename.  We use "con-" which is not a possible wiki name, for the local name .
        wikiName="con"
    pageData=client.ServerProxy(url).pages.get_one({"site" :site_name, "page" : wikiName})

    # Get the updated time for the local version
    localUpdatedTime=None
    if os.path.isfile(localName+ ".xml"):
        tree=ET.parse(localName + ".xml")
        doc=tree.getroot()
        localUpdatedTime=doc.find("updated_at").text

    # Write the page source to <saveName>.txt
    if pageData.get("content", None) != None:
        with open(localName + ".txt", "wb") as file:
            file.write(pageData["content"].encode("utf8"))

    if pageData.get("html", None) != None:
        with open(localName + ".html", "wb") as file:
            file.write(pageData["html"].encode("utf8"))

    # Write the rest of the page's data to <saveName>.xml
    wikiUpdatedTime = SaveMetadata(localName, pageData)

    # Check for attached files
    fileNameList=client.ServerProxy(url).files.select({"site":site_name, "page": wikiName})
    if len(fileNameList) > 0:
        if not os.path.exists(localName):
            os.mkdir(localName)   # Create a directory for the files and metadata
            os.chmod(localName, 0o777)
        for fileName in fileNameList:
            path = os.path.join(os.getcwd(), localName, fileName)

            meta_data = client.ServerProxy(url).files.get_meta({"site" : site_name, "page": wikiName, "files": [fileName]})
            assert len(meta_data.keys()) == 1

            meta_data = meta_data[list(meta_data.keys())[0]]

            dl_url = meta_data['download_url']
            r = requests.get(dl_url, allow_redirects=True)
            r.raise_for_status()

            #content=base64.b64decode(fileStuff["content"])
            with open(path, "wb+") as file:
                file.write(r.content)     # Save the content

            # Now the metadata
            SaveMetadata(os.path.join(localName, fileName), meta_data)

    # We return True whenever we have just downloaded a page which was already up-to-date locally
    tWiki=DecodeDatetime(wikiUpdatedTime)
    tLocal=DecodeDatetime(localUpdatedTime)

    return tWiki>tLocal


def SaveMetadata(localName, pageData):
    root = ET.Element("data")
    wikiUpdatedTime = None
    for itemName in pageData:
        if itemName == "content" or itemName == "html":  # We've already dealt with this
            continue
        if itemName == "tags":
            tags = pageData["tags"]
            if len(tags) > 0:
                tagsElement = ET.SubElement(root, "tags")
                for tag in tags:
                    tagElement = ET.SubElement(tagsElement, "tag")
                    tagElement.text = tag
            continue
        if itemName == "updated_at":  # Save the updated time
            wikiUpdatedTime = pageData[itemName]
        if pageData[itemName] != None and pageData[itemName] != "None":
            element = ET.SubElement(root, itemName)
            element.text = str(pageData[itemName])

    # And write it out.
    tree = ET.ElementTree(root)
    tree.write(localName + ".xml")
    return wikiUpdatedTime

# ---------------------------------------------
# Main


def run_multi(api_key : str, *site_names, output_folder = Path(__file__).parent / 'sites2/'):

    for site_n in site_names:
        url = f'https://{site_n}:{api_key}@www.wikidot.com/xml-rpc-api.php'
        print(f'Downloading {url}')
        run(site_n, url, output_folder)

def run(site_name : str, url : str, output_path_base : str):
    """
    Args:
        site_name (str): Site to update/download
        api_key (str): User API key
    """

    # Change the working directory to the destination of the downloaded wiki
    output_path = output_path_base / site_name
    output_path.mkdir(exist_ok=True)
    os.chdir(str(output_path))

    # Now, get list of recently modified pages.  It will be ordered from most-recently-updated to least.
    print("Get list of all pages from Wikidot, sorted from most- to least-recently-updated")
    listOfAllWikiPages=client.ServerProxy(url).pages.select({"site" : site_name, "order": "updated_at desc"})
    listOfAllWikiPages=[name.replace(":", "_", 1) for name in listOfAllWikiPages]   # replace the first ":" with "_" in all page names
    listOfAllWikiPages=[name if name != "con" else "con-" for name in listOfAllWikiPages]   # Handle the "con" special case

    # # Download the recently updated pages until we start finding pages we already have
    # print("Downloading recently updated pages...")
    # for pageName in listOfAllWikiPages:
    #     if not DownloadPage(pageName, site_name, url):  # Quit as soon as we start re-loading pages which have not been updated
    #         print("      Page is up-to-date. Ending downloads")
    #         break

    # # Get the page list from the local directory and use that to create lists of missing pages and deleted pages
    # print("Creating list of local files")
    # list = os.listdir(".")
    # # Since all local copies of pages have a .txt file, listOfAllDirPages will contain the file name of each page (less the extension)
    # # So we want a list of just those names stripped of the extension
    # listOfAllDirPages=[p[:-4] for p in list if p.endswith(".txt")]

    # # Now figure out what pages are missing and download them.
    # print("Downloading missing pages...")
    # listOfAllMissingPages = [val for val in listOfAllWikiPages if val not in listOfAllDirPages]  # Create a list of pages which are in the wiki and not downloaded
    # if len(listOfAllMissingPages) == 0:
    #     print("   There are no missing pages")

    for pageName in listOfAllWikiPages:
        if pageName[0] != '_':
            DownloadPage(pageName, site_name, url)

    # And delete local copies of pages which have disappeared from the wiki
    # Note that we don't detect and delete local copies of attached files which have been removed from the wiki.
    # print("Removing deleted pages...")
    # listOfAllDeletedPages = [val for val in listOfAllDirPages if val not in listOfAllWikiPages]  # Create a list of pages which are dowloaded but not in the wiki
    # if len(listOfAllDeletedPages) == 0:
    #     print("   There are no pages to delete")
    # for pageName in listOfAllDeletedPages:
    #     print("   Removing: " + pageName)
    #     if os.path.isfile(pageName + ".xml"):
    #         os.remove(pageName + ".xml")
    #     if os.path.isfile(pageName + ".html"):
    #         os.remove(pageName + ".html")
    #     if os.path.isfile(pageName + ".txt"):
    #         os.remove(pageName + ".txt")

    print("Done")

if __name__ == '__main__':
    fire.Fire(run_multi)

