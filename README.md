# myP2PSync
SW applications system able to share and synchronize files among several devices using P2P file-sharing techniques. 

The aim of the project is to develop a system that keeps updated copies of files between different machines belonging to the same "synchronization group".
The update operation is not real-time, but just when the user decides to synchronize his version with all the other device.
Access to a particular group is a function of a key that must be possessed and the procedure is managed by a central server.
The sharing of the modified file is in P2P between the different terminals.
A peer can belong to different groups, covering different roles.
Roles: Master (usually the creator of the group, a privilege that can be reassigned maybe in the future), Reader/Writer (can modify the file and request that it be updated in the cloud), Reader (can only read the file, not edit).

