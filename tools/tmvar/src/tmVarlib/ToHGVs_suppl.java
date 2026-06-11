package tmVarlib;
//
// tmVar - Java version
//

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.UnsupportedEncodingException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

import javax.xml.stream.XMLStreamException;

import bioc.BioCCollection;
import bioc.io.woodstox.ConnectorWoodstox;

public class ToHGVs_suppl
{
	/*
	 * Tab format
	 */
	public static void ToHGVs_Suppl(String InputFile,String OutputFile) throws IOException
	{
		BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
		BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile), "UTF-8"));
		String line="";
		while ((line = br.readLine()) != null)  
		{
			Pattern patt = Pattern.compile("^([0-9]*)	(PMC[0-9]+)	([^\t]+)	([^\t]+)");
			Matcher mat = patt.matcher(line);
			if(mat.find()) 
	        {
				String pmid=mat.group(1);
				String pmcid=mat.group(2);
				String NormalizedVar=mat.group(3);
				String OriginalVar=mat.group(4);
				NormalizedVar=NormalizedVar.replaceAll(",[A-Z]$","");
				OriginalVar=OriginalVar.replaceAll(",[A-Z]$","");
				OriginalVar=OriginalVar.replaceAll(",[A-Z]\\|","\\|");
				String ID_HGVs="";
				String component[]=NormalizedVar.split("\\|",-1);
				
				if(NormalizedVar.matches("^rs[0-9]+$"))
				{
					bw.write(pmid+"\t"+pmcid+"\t"+NormalizedVar+"\t"+OriginalVar+"\n");
				}
				else if(component[0].equals("p"))
				{
					if(component[1].equals("SUB"))
					{
						ID_HGVs=component[0]+"."+component[2]+component[3]+component[4];
					}
					else if(component[1].equals("INS")) //"c.104insT"	--> "c|INS|104|T"
					{
						ID_HGVs=component[0]+"."+component[2]+"ins"+component[3];
					}
					else if(component[1].equals("DEL")) //"c.104delT"	--> "c|DEL|104|T"
					{
						ID_HGVs=component[0]+"."+component[2]+"del"+component[3];
					}
					else if(component[1].equals("INDEL")) //"c.2153_2155delinsTCCTGGTTTA"	-->	"c|INDEL|2153_2155|TCCTGGTTTA"
					{
						ID_HGVs=component[0]+"."+component[2]+"delins"+component[3];
					}
					else if(component[1].equals("DUP")) //"c.1285-1301dup"	--> "c|DUP|1285_1301||"
					{
						ID_HGVs=component[0]+"."+component[2]+"dup"+component[3];
					}
					else if(component[1].equals("FS")) //"p.Val35AlafsX25"	-->	"p|FS|V|35|A|25"
					{
						if(component.length>5)
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
						else if(component.length>4)
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX";
						}
						else
						{
							ID_HGVs=OriginalVar;
						}
					}
					bw.write(pmid+"\t"+pmcid+"\t"+ID_HGVs+"\t"+OriginalVar+"\n");
				}
				else if(component[0].equals("c") || component[0].equals("g"))
				{
					if(component[1].equals("SUB"))
					{
						ID_HGVs=component[0]+"."+component[3]+component[2]+">"+component[4];
					}
					else if(component[1].equals("INS"))
					{
						ID_HGVs=component[0]+"."+component[2]+"ins"+component[3];
					}
					else if(component[1].equals("DEL"))
					{
						ID_HGVs=component[0]+"."+component[2]+"del"+component[3];
					}
					else if(component[1].equals("INDEL"))
					{
						ID_HGVs=component[0]+"."+component[2]+"delins"+component[3];
					}
					else if(component[1].equals("DUP"))
					{
						ID_HGVs=component[0]+"."+component[2]+"dup"+component[3];
					}
					else if(component[1].equals("FS"))
					{
						if(component.length>5)
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
						else if(component.length>4)
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX";
						}
						else
						{
							ID_HGVs=OriginalVar;
						}
					}
					bw.write(pmid+"\t"+pmcid+"\t"+ID_HGVs+"\t"+OriginalVar+"\n");
				}
				else if(component[0].equals(""))
				{
					if(component[1].equals("SUB"))
					{
						ID_HGVs="c."+component[3]+component[2]+">"+component[4];
					}
					else if(component[1].equals("INS"))
					{
						ID_HGVs="c."+component[2]+"ins"+component[3];
					}
					else if(component[1].equals("DEL"))
					{
						ID_HGVs="c."+component[2]+"del"+component[3];
					}
					else if(component[1].equals("INDEL"))
					{
						ID_HGVs="c."+component[2]+"delins"+component[3];
					}
					else if(component[1].equals("DUP"))
					{
						ID_HGVs="c."+component[2]+"dup"+component[3];
					}
					else if(component[1].equals("FS"))
					{
						if(component.length>5)
						{
							ID_HGVs="p."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
						else if(component.length>4)
						{
							ID_HGVs="p."+component[2]+component[3]+component[4]+"fsX";
						}
						else
						{
							ID_HGVs=OriginalVar;
						}
						
					}
					bw.write(pmid+"\t"+pmcid+"\t"+ID_HGVs+"\t"+OriginalVar+"\n");
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
	public static void main(String [] args) throws IOException, InterruptedException, XMLStreamException, SQLException 
	{
		String InputFile="output/tmVar.txt";
		String OutputFile="output/tmVar.HGVs.txt";
		if(args.length<1)
		{
			System.out.println("\n$ java -Xmx5G -Xms5G -jar ToHGVs.jar [InputFile] [OutputFile]");
		}
		else
		{
			InputFile=args [0];
			OutputFile=args [1];
		}	
			
		double startTime,endTime,totTime;
		startTime = System.currentTimeMillis();//start time
		
		File f = new File(OutputFile);
		if(f.exists() && !f.isDirectory()) 
		{ 
			System.out.println(InputFile+" - Done. (The output file exists)");
		}
		else
		{
			ToHGVs_Suppl(InputFile,OutputFile);
			
			/*
			 * Time stamp - last
			 */
			endTime = System.currentTimeMillis();//ending time
			totTime = endTime - startTime;
			System.out.println(InputFile+" - Processing Time:"+totTime/1000+"sec");
		}
	}
}
