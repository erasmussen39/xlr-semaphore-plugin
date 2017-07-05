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
from com.xebialabs.deployit.exception import NotFoundException
from com.xebialabs.xlrelease.api.v1.forms import Variable

current_milli_time = lambda: int(round(time.time() * 1000))

class SemaphoreClient(object):
    def __init__(self, current_release, current_phase, configuration_api, release_api, phase_api):
        self.release = current_release
        self.phase = current_phase
        self.config_api = configuration_api
        self.release_api = release_api
        self.phase_api = phase_api
        return

    @staticmethod
    def get_client(current_release, current_phase, configuration_api, release_api, phase_api):
        return SemaphoreClient(current_release, current_phase, configuration_api, release_api, phase_api)

    def get_db(self, name, global_vars):
        if name is None or not name:
            name = "DEFAULT_SEMAPHORE_DB"
        key = "global.%s" % name
        db = None
        for v in global_vars:
            if v.key == key:
                db = v
        if db is not None:
            return db
        else:
            self.initialize_db(name)
            return self.get_db(name, self.config_api.globalVariables)

    def refresh_db(self, db):
        return self.config_api.getGlobalVariable(db.getId())

    def initialize_db(self, name):
        db = Variable()
        db.requiresValue = False
        db.showOnReleaseStart = False
        db.setType("xlrelease.MapStringStringVariable")
        mapping = {}
        db.setValue(mapping)
        db.setKey("global.%s" % name)
        self.config_api.addGlobalVariable(db)

    def update_db(self, db):
        self.config_api.updateGlobalVariable(db)

    def force_unlock_db(self, db, key):
        db = self.refresh_db(db)
        mapping = db.getValue()
        del mapping['%s_UNLOCK_HASH' % key]
        db.setValue(mapping)
        self.update_db(db)

    def is_locked(self, db, key):
        locked = '%s_UNLOCK_HASH' % key in db.getValue()
        if not locked:
            print "Key: %s not found in DB: %s -- NOT LOCKED" % (key, db.getKey())
            return False
        else:
            # Check release status and phases status for end cases.
            unlock_hash = db.getValue()['%s_UNLOCK_HASH' % key]
            lock_info = base64.b64decode(unlock_hash).split(',')
            release_id = lock_info[0]
            phase_id = lock_info[1]
            try:
                release = self.release_api.getRelease(release_id)
                release_status = release.getStatus()
                if str(release_status) in {'ABORTED', 'COMPLETED'}:
                    print "Release: %s associated with Key: %s in DB: %s had status: %s -- UNLOCKED" % (release_id, key, db.getKey(), release_status)
                    self.force_unlock_db(db, key)
                    return False
            except NotFoundException:
                # Release no longer exists (archived), force a release of the lock.
                print "Release: %s associated with Key: %s in DB: %s no longer exists -- UNLOCKED" % (release_id, key, db.getKey())
                self.force_unlock_db(db, key)
                return False
            phase = self.phase_api.getPhase(phase_id)
            phase_status = phase.getStatus()
            if str(phase_status) in {'ABORTED', 'COMPLETED', 'SKIPPED'}:
                print "Phase: %s associated with Key: %s in DB: %s and Release: %s had status: %s -- UNLOCKED" % (release_id, key, db.getKey(), release_id, phase_status)
                self.force_unlock_db(db, key)
                return False
        print "Key: %s in DB: %s -- LOCKED -- by Release: %s" % (key, db.getKey(), release_id)
        return True

    def core_lock(self, variables):
        db_name = variables['repository_name']
        db = self.get_db(db_name, self.config_api.globalVariables)
        while self.is_locked(db, variables['key']):
            time.sleep(variables['polling_interval'])
            db = self.refresh_db(db)
        db = self.refresh_db(db)
        unlock_hash = base64.b64encode("%s,%s,%s" % (self.release.getId(), self.phase.getId(), str(current_milli_time())))
        mapping = db.getValue()
        mapping['%s_UNLOCK_HASH' % variables['key']] = unlock_hash
        db.setValue(mapping)
        self.update_db(db)
        return {'output': unlock_hash}

    def core_unlock(self, variables):
        if variables['unlock_hash'] is None:
            raise Exception("You must specify the unlock hash.")
        db_name = variables['repository_name']
        db = self.get_db(db_name, self.config_api.globalVariables)
        mapping = db.getValue()
        found = False
        for key, value in mapping.items():
            if value == variables['unlock_hash']:
                del mapping[key]
                found = True
        if not found:
            raise Exception("Could not locate specified hash: %s" % variables['unlock_hash'])
        db.setValue(mapping)
        self.update_db(db)
        return {'output': 'unlocked hash: %s from reppository db: %s' % (variables['unlock_hash'], db_name)}
