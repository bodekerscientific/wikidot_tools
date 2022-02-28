# A package to support API access to Wikidot

# *****************************************************************
# Return a Wikidot cannonicized version of a name
# The cannonicized name turns all spans of non-alphanumeric characters into a single hyphen, drops all leading and trailing hyphens
# and turns all alphabetic characters to lower case
# A Raw name is a single string possibly including a category: prefix
cannonicalToReal = {}   # A dictionary which lets us go from cannonical names back to real names


# We need to convert a string to Wikidot's cannonical form: All lower case; All spans of special characters reduced to a hyphen; No leading ro trailing hyphens.
# The strategy is to iterate through the name, copying characters to a list of characters which is later merged into the return string. (Appending to a string is too expensive.)
def CannonicizeString(name):
    out = []
    inAlpha = False
    inJunk = False
    for c in name:
        if c.isalnum() or c == ':':     # ":", the category separator, is an honorary alphanumeric
            if inJunk:
                out.append("-")
            out.append(c)
            inJunk = False
            inAlpha = True
        else:
            inJunk = True
            inAlpha = False
    # Remove any leading or trailing "-"
    canname=''.join(out)
    if canname[0] == "-":
        canname=canname[1:]
    if canname[:-1] == "-":
        canname=canname[:-1]
    return canname

# Take a raw name (mixed case, special characters, a potential category, etc.) and turn it into a properly formatted cannonicized name:
#       Either "<category>:<name>" or, when there is no category, just "<name>"
#       In both cases, the <> text is cannonicized
def Cannonicize(pageNameZip):
    if pageNameZip == None:
        return None
    pageName = pageNameZip.lower()

    # Split out the category, if any.
    splitName=pageName.split(":")
    if len(splitName) > 2:
        splitName=[splitName[0], " ".join(splitName[1:])]  # Assume first colon is the category divider.  The rest will eventually be ignored

    # Handle the case of no category
    if len(splitName) == 1:
        canName=CannonicizeString(splitName[0])
        name=splitName[0]
    else:
        canName=CannonicizeString(splitName[0])+":"+CannonicizeString(splitName[1])
        name=splitName[0]+":"+splitName[1]

    # And save the cannocized and raw versions of the name in a reverse-lookup dictionary
    if cannonicalToReal.get(canName) == None:
        cannonicalToReal[canName]=name  # Add this cannonical-to-real conversion to the dictionary
    return canName


# *****************************************************************
# Potentially add this entry to the list of uncannonicized page names
def AddUncannonicalName(uncanName, canName):
    if cannonicalToReal.get(canName) == None:
        cannonicalToReal[canName]=uncanName
    else:
        if ([x.isupper() for x in uncanName].count(True) > [x.isupper() for x in cannonicalToReal[canName]].count(True)):
            cannonicalToReal[canName]=uncanName


# *****************************************************************
def Uncannonicize(name):
    n=cannonicalToReal.get(name)
    if n != None:
        return n

    # OK, this is most likely the name of a redirect page.  The best we can do is to remove internal hyphens.
    # (We need to do better here!)
    return name.replace("-", "")


# *****************************************************************
# Is the page a redirect?  If yes, return the cannonicized redirect; if not, return null
# A redirect is of the form [[module Redirect destination="<dest>"]]
# We want to return the cannonicized destination or None if it is not a redirect
def IsRedirect(pageText):
    pageText = pageText.strip()  # Remove leading and trailing whitespace
    if pageText.lower().startswith('[[module redirect destination="') and pageText.endswith('"]]'):
        return Cannonicize(pageText[31:].rstrip('"]'))
    return None


# *****************************************************************
# Should this filename be ignored?
# Return value is either the cleaned filename or None if the file should be ignored.
def InterestingFilenameZip(filenameZip):

    if not filenameZip.startswith("source/"):    # We're only interested in source files
        return None
    if len(filenameZip) <= 11:  # There needs to be something there besides 'source/.txt'
           return None

    # These files are specific to Fancyclopedia and are known to be ignorable
    if filenameZip.startswith("source/index_people"):  # Pages with names "source/index_people..." are index pages, not content pages.
        return None
    if filenameZip.startswith("source/index_alphanumeric"):  # Likewise
        return None
    if filenameZip.startswith("source/testing_alphanumeric"):  # Likewise
        return None

    return filenameZip[7:-4]  # Drop "source/" and ".txt", returning the cleaned name


# *****************************************************************
# Read a source file from a zipped Wikidot backup
def ReadPageSourceFromZip(zip, filename):

    if InterestingFilenameZip(filename) == None:
        return None

    source = zip.read(filename).decode("utf-8")
    if source == None:
        print("error: '" + filename + "' read as None")
        exit
    return source

# *****************************************************************
# Convert the filename in a zipped Wikidot backup (which uses "_" to indicate a category) to use a Wikidot ":" category indicator
# Change <category>:<name> to <category>_<name>
def ConvertZipCategoryMarker(name):
    return name.replace(":", "_", 1)