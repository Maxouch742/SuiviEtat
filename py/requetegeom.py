import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import json
import psycopg2
from urllib.parse import urlparse
import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely import ops
import matplotlib.pyplot as plt

# Paramètre du serveur de la base de données
hostName = "localhost"
hostPort = 8000


class MyServer(BaseHTTPRequestHandler) :

    # Connexion à la base de données
    data = {}
    try:
        conn = psycopg2.connect(dbname="YLB_hopital",
                                user="postgres",
                                password="postgres",
                                host="localhost",
                                port="5433")
        cursor = conn.cursor()
        print("Connexion DB : reussie")
    except:
        print("Connexion DB : echec")


    # Headers standards pour répondre du JSON
    def _set_headers(self) :
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS, POST')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # Méthode utile pour le GET
    def do_GET(self) :
        # Variables d'exports
        data_export = []

        # Parsage de l'url pour récupérer la requête souhaitée
        results = urlparse(self.path)

        # afficher les points sur les routes
        if results.query == 'points' :
            
            # Exécution de la requête et réception des données
            self.cursor.execute("SELECT st_astext(st_transform(geom, 2056)), source, target FROM ylb_quartierhopital_v2;")
            self.data = self.cursor.fetchall()

            # Traitement du resultat
            data_export = self.traitementDataAndInterpolate(self.data)
            

        # Afficher la première route
        if results.query == 'FirstRoad' :

            # Exécution de la requête et réception des données
            self.cursor.execute("SELECT st_astext(st_transform(geom, 2056)), source, target FROM ylb_quartierhopital_v2 ORDER BY ST_Length(geom) DESC LIMIT 1;")
            self.data = self.cursor.fetchall()

            # Traitement du resultat
            data_export = self.traitementData(self.data[0])

        # Afficher la route suivante
        if 'road:' in results.query :
            # recupérer la target
            parameter = results.query.split(':')
            target = parameter[1]

            # Lancement de la requête SQL
            self.cursor.execute("SELECT gid, source, target, st_astext(st_transform(geom, 2056)) FROM ylb_quartierhopital_v2 WHERE source = {:d} LIMIT 3;".format(int(target)))
            self.data = self.cursor.fetchall()

            # Traitement du resultat
            print(self.data)
            data_export = self.traitementData_MultiplesRoads(self.data)
        
        print("send data :", data_export)

        # Envoi des données
        self.send_response(200)
        self._set_headers()
        # conversion dict in JSON et écriture du fichier
        self.wfile.write(bytes(json.dumps(data_export), "utf-8"))
    

    def traitementData(self, data) :
            """ Traitement de la requête en faire un JSON avec la géométrie, la source et la target (pg_routing)

            Parameters
            ----------
            data : string
                resultat de la requete SQL dans la database

            Returns
            -------
            data_export : dict
                dictionnaire de la forme suivante :
                { 'coordinates' : [],
                  'source' : int,
                  'target' : int }
            """
            liste_coor_str = data[0]
            #Récupérer l'ensemble des coordonnées en une liste (parsage avec la virgule)
            liste_coor_str = liste_coor_str[17:len(liste_coor_str)-2].split(',')
            coordinates = []
            for element in liste_coor_str :
                data_element = element.split(' ')
                coordinates.append([float(data_element[0]),float(data_element[1])])
            data_export = {}
            data_export.update({'coordinates':coordinates})
            data_export.update({'source':data[1]})
            data_export.update({'target':data[2]})

            return data_export
    

    def traitementDataAndInterpolate(self, data) :
        """ Fonction pour traiter la réponse reçue avec une interpolation des données sur la route

        Args:
            data (list): liste des éléments de la table ylb_quartierhopital_v2 (avec SQL)

        Returns:
            dict: dict avec une liste de tuple avec les coordonnées des points 
        """
        exportData = {}
        Multiline = []

        # Parcours et traitement des données reçues
        for element in data :
            data_list = element[0][17:len(element[0])-2].split(',')
            route = []
            for element in data_list :
                if ')' in element :
                    data_coordinates = element[:-1].split(' ')
                elif '(' in element :
                    data_coordinates = element[1:].split(' ')
                else :
                    data_coordinates = element.split(' ')
                route.append((float(data_coordinates[0]),float(data_coordinates[1])))
            Multiline.append(route)
    
            multiLineString = MultiLineString(Multiline)

        # Merge des features pour créer un réseau global
        mergedRoad = ops.linemerge(multiLineString)

        # Densifier les points sur le réseau
        lenSpace = np.linspace(0,mergedRoad.length,500)
        tempList = []
        for space in lenSpace:
            tempPoint = mergedRoad.interpolate(space)
            tempList.append([tempPoint.x, tempPoint.y])
        exportData.update({'coordinates':tempList})

        # Réponse du réseau
        return tempList
    

    def traitementData_MultiplesRoads(self, roads) :
        """ Traitement de la réponse reçue de la BD pour afficher plusieurs routes
        
        Args:
            roads (list) : liste des divers éléments reçues de la BD
        
        Returns :
            results (dict) : dictionnaire avec les 3 routes max
        """
        # Dictionnaire de réponse
        print('roads',roads)
        results = []

        # Parcours et traitement des données reçues
        for element in roads :
            print(element)
            gid = element[0]
            source = element[1]
            target = element[2]
            data_list = element[3][17:len(element[3])-2].split(',')
            route = []
            for element in data_list :
                if ')' in element :
                    data_coordinates = element[:-1].split(' ')
                elif '(' in element :
                    data_coordinates = element[1:].split(' ')
                else :
                    data_coordinates = element.split(' ')
                route.append((float(data_coordinates[0]),float(data_coordinates[1])))
            results.append({'gid':gid,
                            'source':source,
                            'target':target,
                            'coordinates':route})
        
        return results
           
    


# Programme principal
if __name__ == "__main__" :
    myServer = HTTPServer((hostName, hostPort), MyServer)
    print("-> ",time.asctime(), "Server starts - %s:%s" % (hostName, hostPort))

    try:
        myServer.serve_forever()
    except KeyboardInterrupt:
        pass

    myServer.server_close()
    print("-> ",time.asctime(), "Server stops - %s:%s" % (hostName, hostPort))