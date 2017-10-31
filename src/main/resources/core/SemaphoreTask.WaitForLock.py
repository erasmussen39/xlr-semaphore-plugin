#
# Copyright 2017 XEBIALABS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import base64, time
from core.SemaphoreClient import SemaphoreClient

current_milli_time = lambda: int(round(time.time() * 1000))

client = SemaphoreClient.get_client(getCurrentRelease(), getCurrentPhase(), configurationApi, releaseApi, phaseApi)
db = client.get_db(repository_name)

if client.is_locked(db, key):
    if repository_name:
        db_name = repository_name
    else:
        db_name = "DEFAULT_SEMAPHORE_DB"
    task.setStatusLine("Waiting for lock on key: %s in db: %s" % (key, db_name))
    task.schedule("core/SemaphoreTask.WaitForLock.py", polling_interval)
else:
    db = client.get_db(repository_name)
    unlock_hash = base64.b64encode("%s,%s,%s" % (release.getId(), phase.getId(), str(current_milli_time())))
    mapping = db.getValue()
    mapping['%s_UNLOCK_HASH' % key] = unlock_hash
    db.setValue(mapping)
    client.update_db(db)
    output = unlock_hash
