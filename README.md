# myLocalP2PSyncCloud
SW applications system able to share and synchronize files among several devices using P2P file-sharing techniques. 

Vision
The aim of the project is to develop a local cloud system that keeps updated copies of files between different machines belonging to the same "synchronization group".
The update operation is not real-time, but just when the user decides to synchronize his version with all the other device.
Access to a particular group is a function of a key that must be possessed and the procedure is managed by a central server.
Changes to a certain file by one of the machines are synchronized with other machines but the master can accepts it or not (in case not have to restore a previous version). The sharing of the modified file is in P2P between the different terminals.
A peer can belong to different groups, covering different roles.
Example of hierarchy of roles: Master (usually the creator of the group, a privilege that can be reassigned maybe in the future), Reader/Writer (can modify the file and request that it be updated in the cloud), Reader (can only read the file, not edit)."

Characteristics of the system
No real-time synchronization (it's really too difficult to implement)
Privilege management (by the master)
Managing of the synchronization issue (pull / push / merge approach like GitHub can be a solution)
Possibility to recover a previous version of a file (by the Master)
Torrent-like approach where the synchronization source works as a tracker (provide peers list)
In the synchronization (file sharing) phase the P2P protocol is similar to that of BitTorrent (chunks, elective)
Programming language: Python, PyQT, QT Designer
