package db;
//
// https://bitbucket.org/xerial/sqlite-jdbc/downloads --> sqlite-jdbc-3.8.11.2.jar
// Add to build path
//

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.util.HashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.xml.stream.XMLInputFactory;
import javax.xml.stream.XMLStreamConstants;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamReader;
import javax.xml.stream.events.StartElement;
import javax.xml.stream.events.XMLEvent;

public class MatchLocation
{
	public static boolean Compare_RSnum_MutationID(String RSnumber,int mutation_mention_location) throws InterruptedException, ClassNotFoundException, IOException, XMLStreamException 
	{
		//Eutils --> dbsnp
		URL URL_eutils = new URL("http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=snp&mode=xml&id="+RSnumber);
		HttpURLConnection conn_eutils = (HttpURLConnection) URL_eutils.openConnection();
		conn_eutils.setDoOutput(true);
		OutputStream os_eutils = conn_eutils.getOutputStream();
		//parsing XML
		XMLInputFactory xmlif = XMLInputFactory.newInstance();
		XMLStreamReader xmlr = xmlif.createXMLStreamReader("HGVs", conn_eutils.getInputStream());
		while (xmlr.hasNext()) 
		{
			int eventType = xmlr.getEventType();
		    eventType = xmlr.next();
		    if (eventType == XMLStreamConstants.START_ELEMENT) 
		    {
		        if(xmlr.getLocalName().equals("hgvs")) // only extract the hgvs tags
        		{
		        	String HGVs_string = xmlr.getElementText();
		        	Pattern pat = Pattern.compile("^(NM\\_[0-9\\.\\-\\_]+):c\\.([\\-\\+]*[0-9]+)");
		        	Matcher mat = pat.matcher(HGVs_string);
		        	if(mat.find()) 
		        	{
		        		String nuccore_id = mat.group(1);
		        		int hgvs_location=Integer.parseInt(mat.group(2)); //hgvs_location
		        		
						//Eutils --> nuccore
						URL URL_nuccore = new URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nucleotide&mode=xml&id="+nuccore_id);
						HttpURLConnection conn_nuccore = (HttpURLConnection) URL_nuccore.openConnection();
		    			conn_nuccore.setDoOutput(true);
		    			OutputStream os_nuccore = conn_nuccore.getOutputStream();
		    			BufferedReader br_nuccore = new BufferedReader(new InputStreamReader(conn_nuccore.getInputStream()));
		    			String STR_nuccore="";
		    			String line_nuccore="";
		    			while((line_nuccore = br_nuccore.readLine()) != null)
		    			{
		    				STR_nuccore=STR_nuccore+line_nuccore;
		    			}
		    			STR_nuccore=STR_nuccore.replaceAll("[ ]+"," ");
		    			Pattern pat_nuccore = Pattern.compile("data cdregion.*? from ([0-9]+) , to [0-9]+");
			        	Matcher mat_nuccore = pat_nuccore.matcher(STR_nuccore);
			        	if(mat_nuccore.find()) 
			        	{
			        		int CDS_start = Integer.parseInt(mat_nuccore.group(1));
			        		if(mutation_mention_location == hgvs_location+CDS_start)
			        		{
			        			return true;
			        		}
			        	}
		        	}
        		}
		    }
		}
		return false;
	}
	public static void LocationFinding(String InputFile,String OutputFile) throws InterruptedException, ClassNotFoundException, IOException, XMLStreamException 
	{
		BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile), "UTF-8"));
		BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
		HashMap <String,String> RSnumber2found = new HashMap <String,String>();
		String line="";
		while ((line = br.readLine()) != null)  
		{
			//FN	24057245	12979860	c|SUB|C|-3176|T
			String column [] = line.split("\\t");
			String result=column[0];
			String pmid=column[1];
			String RSnumber=column[2];
			String mutation_id=column[3];
			String mutation_id_component[] =  mutation_id.split("\\|");
			if(mutation_id_component[3].matches("[\\+\\-]*[0-9]+"))
			{
				int mutation_mention_location = Integer.parseInt(mutation_id_component[3]); //mutation_mention_location
				
				//Compare_RSnum_MutationID
				boolean foundYN = Compare_RSnum_MutationID(RSnumber,mutation_mention_location);
				if(RSnumber2found.containsKey(RSnumber+"\t"+mutation_mention_location))
				{
					if(RSnumber2found.get(RSnumber+"\t"+mutation_mention_location).equals("Yes"))
					{
						System.out.println(line+"\tFound");
						bw.write(line+"\tFound\n");
					}
					else
					{
						System.out.println(line);
						bw.write(line+"\n");
					}
				}
				else if(foundYN)
				{	
					RSnumber2found.put(RSnumber+"\t"+mutation_mention_location, "Yes");
					System.out.println(line+"\tFound");
					bw.write(line+"\tFound\n");
				}
				else
				{
					RSnumber2found.put(RSnumber+"\t"+mutation_mention_location, "No");
					System.out.println(line);
					bw.write(line+"\n");
				}
			}
			else
			{
				bw.write(line+"\n");
			}
		}
		br.close();
		bw.close();
	}
	public static void main(String [] args) throws ClassNotFoundException, InterruptedException, IOException, XMLStreamException
	{
		String InputFile= "";
		String OutputFile = "";
		if(args.length<2)
		{
			System.out.println("\n$ java -Xmx5G -Xms5G -jar MatchLocation.jar [InputFile] [OutputFile]");
			InputFile="FNFP/FNFP.txt";
			OutputFile="FNFP/FNFP.rev.txt";
		}
		else
		{
			InputFile= args[0];
			OutputFile = args[1];
		}
		LocationFinding(InputFile,OutputFile);
	}
}
