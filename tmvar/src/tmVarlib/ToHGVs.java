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
import java.io.InputStream;
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

public class ToHGVs
{
	public static HashMap<String,String> nametothree = new HashMap<String,String>();
	public static HashMap<String,String> threetone = new HashMap<String,String>();
	public static HashMap<String,String> threetone_nu = new HashMap<String,String>();
	public static HashMap<String,String> NTtoATCG = new HashMap<String,String>();
	public static HashMap<String,String> VariantType_hash = new HashMap<String,String>();
	public static HashMap<String,String> Number_word2digit = new HashMap<String,String>();
	
	/*
	 * BioCXML/PubTator format
	 */
	public static String BioCFormatCheck(String InputFile) throws IOException
	{
		
		ConnectorWoodstox connector = new ConnectorWoodstox();
		BioCCollection collection = new BioCCollection();
		try
		{
			collection = connector.startRead(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
		}
		catch (UnsupportedEncodingException | FileNotFoundException | XMLStreamException e) 
		{
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
			String line="";
			String status="";
			String Pmid = "";
			boolean tiabs=false;
			Pattern patt = Pattern.compile("^([^\\|\\t]+)\\|([^\\|\\t]+)\\|(.*)$");
			while ((line = br.readLine()) != null)  
			{
				Matcher mat = patt.matcher(line);
				if(mat.find()) //Title|Abstract
	        	{
					if(Pmid.equals(""))
					{
						Pmid = mat.group(1);
					}
					else if(!Pmid.equals(mat.group(1)))
					{
						return "[Error]: "+InputFile+" - A blank is needed between "+Pmid+" and "+mat.group(1)+".";
					}
					status = "tiabs";
					tiabs = true;
	        	}
				else if (line.contains("\t")) //Annotation
	        	{
	        	}
				else if(line.length()==0) //Processing
				{
					if(status.equals(""))
					{
						if(Pmid.equals(""))
						{
							return "[Error]: "+InputFile+" - It's not either BioC or PubTator format.";
						}
						else
						{
							return "[Error]: "+InputFile+" - A redundant blank is after "+Pmid+".";
						}
					}
					Pmid="";
					status="";
				}
			}
			br.close();
			if(tiabs == false)
			{
				return "[Error]: "+InputFile+" - It's not either BioC or PubTator format.";
			}
			if(status.equals(""))
			{
				return "PubTator";
			}
			else
			{
				return "[Error]: "+InputFile+" - The last column missed a blank.";
			}
		}
		return "BioC";
	}
	public static void ToHGVs_PubTator(String InputFile,String OutputFile) throws IOException
	{
		BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
		BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile), "UTF-8"));
		String line="";
		while ((line = br.readLine()) != null)  
		{
			Pattern patt = Pattern.compile("^([^\\|\\t]+)\\|([^\\|\\t]+)\\|(.*)$");
			Matcher mat = patt.matcher(line);
			if(mat.find()) //Title|Abstract
	        {
				bw.write(line+"\n");
			}
			else if (line.contains("\t")) //Annotation
        	{
				String anno[]=line.split("\t",-1);
				if(anno[4].matches("(DNAMutation|ProteinMutation|SNP|Mutation|Variation)"))
				{
					String ID=anno[5];
					String ID_HGVs="";
					String VariationInformation="";
					Pattern ptmp = Pattern.compile("([^\\;]+)(;.+)$");
					Matcher mtmp = ptmp.matcher(ID);
					if(mtmp.find())
					{
						ID=mtmp.group(1);
						VariationInformation=mtmp.group(2);
					}
					String component[]=ID.split("\\|",-1);
					if(component[0].equals("p"))
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
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
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
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
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
							ID_HGVs="p."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
					}
					if(ID_HGVs.equals(""))
					{
						ID_HGVs=anno[3];
					}
					bw.write(anno[0]+"\t"+anno[1]+"\t"+anno[2]+"\t"+anno[3]+"\t"+anno[4]+"\t"+ID_HGVs+VariationInformation+"\n");
				}
				else
				{
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
	public static void ToHGVs_BioC(String InputFile,String OutputFile) throws IOException, XMLStreamException
	{
		BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
		String line="";
		String STR="";
		while ((line = br.readLine()) != null)  
		{
			STR=STR+line;
		}
		br.close();
		BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile), "UTF-8"));
		
		String anno[] = STR.split("</annotation>",-1);
		for(int i=0;i<anno.length;i++)
		{
			Pattern patt = Pattern.compile("^(.*<annotation.*?>)(.+?)$");
			Matcher mat = patt.matcher(anno[i]);
			if(mat.find())
			{
				bw.write(mat.group(1));
				String annotation = mat.group(2);
				if(annotation.matches(".*<infon.*?>(Mutation|ProteinMutation|DNAMutation|SNP|Variation)</infon>.*"))
				{
					Pattern patt_id = Pattern.compile("^(.*<infon key[ ]*=[ ]*[\"\'](Identifier|tmVar|identifier|Mutation|Variation)[\"\'][ ]*>)(.+?)(</infon>.*)$");
					Matcher mat_id = patt_id.matcher(annotation);
					if(mat_id.find())
					{
						String pre=mat_id.group(1);
						String ID=mat_id.group(3);
						String post=mat_id.group(4);
						
						String ID_HGVs="";
						String VariationInformation="";
						Pattern ptmp = Pattern.compile("([^\\;]+)(;.+)$");
						Matcher mtmp = ptmp.matcher(ID);
						if(mtmp.find())
						{
							ID=mtmp.group(1);
							VariationInformation=mtmp.group(2);
						}
						String component[]=ID.split("\\|",-1);
						if(component[0].equals("p"))
						{
							if(component[1].equals("SUB") && component.length>=5)
							{
								ID_HGVs=component[0]+"."+component[2]+component[3]+component[4];
							}
							else if(component[1].equals("INS") && component.length>=4) //"c.104insT"	--> "c|INS|104|T"
							{
								ID_HGVs=component[0]+"."+component[2]+"ins"+component[3];
							}
							else if(component[1].equals("DEL") && component.length>=4) //"c.104delT"	--> "c|DEL|104|T"
							{
								ID_HGVs=component[0]+"."+component[2]+"del"+component[3];
							}
							else if(component[1].equals("INDEL") && component.length>=4) //"c.2153_2155delinsTCCTGGTTTA"	-->	"c|INDEL|2153_2155|TCCTGGTTTA"
							{
								ID_HGVs=component[0]+"."+component[2]+"delins"+component[3];
							}
							else if(component[1].equals("DUP") && component.length>=4) //"c.1285-1301dup"	--> "c|DUP|1285_1301||"
							{
								ID_HGVs=component[0]+"."+component[2]+"dup"+component[3];
							}
							else if(component[1].equals("FS") && component.length>=6) //"p.Val35AlafsX25"	-->	"p|FS|V|35|A|25"
							{
								ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
							}
						}
						else if(component[0].equals("c") || component[0].equals("g"))
						{
							if(component[1].equals("SUB") && component.length>=5)
							{
								ID_HGVs=component[0]+"."+component[3]+component[2]+">"+component[4];
							}
							else if(component[1].equals("INS") && component.length>=4)
							{
								ID_HGVs=component[0]+"."+component[2]+"ins"+component[3];
							}
							else if(component[1].equals("DEL") && component.length>=4)
							{
								ID_HGVs=component[0]+"."+component[2]+"del"+component[3];
							}
							else if(component[1].equals("INDEL") && component.length>=4)
							{
								ID_HGVs=component[0]+"."+component[2]+"delins"+component[3];
							}
							else if(component[1].equals("DUP") && component.length>=4)
							{
								ID_HGVs=component[0]+"."+component[2]+"dup"+component[3];
							}
							else if(component[1].equals("FS") && component.length>=6)
							{
								ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
							}
						}
						else if(component[0].equals(""))
						{
							if(component[1].equals("SUB") && component.length>=5)
							{
								ID_HGVs="c."+component[3]+component[2]+">"+component[4];
							}
							else if(component[1].equals("INS") && component.length>=4)
							{
								ID_HGVs="c."+component[2]+"ins"+component[3];
							}
							else if(component[1].equals("DEL") && component.length>=4)
							{
								ID_HGVs="c."+component[2]+"del"+component[3];
							}
							else if(component[1].equals("INDEL") && component.length>=4)
							{
								ID_HGVs="c."+component[2]+"delins"+component[3];
							}
							else if(component[1].equals("DUP") && component.length>=4)
							{
								ID_HGVs="c."+component[2]+"dup"+component[3];
							}
							else if(component[1].equals("FS") && component.length>=6)
							{
								ID_HGVs="p."+component[2]+component[3]+component[4]+"fsX"+component[5];
							}
						}
						if(ID_HGVs.equals(""))
						{
							Pattern patt_text = Pattern.compile("<text>(.+?)</text>");
							Matcher mat_text = patt_text.matcher(annotation);
							if(mat_text.find())
							{
								ID_HGVs=mat_text.group(1);
							}
							else
							{
								ID_HGVs=ID;
							}
							ID_HGVs=ID_HGVs.replaceAll("[^\\~\\!\\@\\#\\$\\%\\^\\&\\*\\(\\)\\_\\+\\{\\}\\|\\:\"\\<\\>\\?\\`\\-\\=\\[\\]\\;\\'\\,\\.\\/\\r\\n0-9a-zA-Z ]","");
						}
						bw.write(pre);
						bw.write(ID_HGVs+VariationInformation);
						bw.write(post);
					}
					else
					{
						bw.write(annotation);
					}
				}
				else
				{
					bw.write(annotation);
				}
			}
			else
			{
				bw.write(anno[i]);
			}
			if(i<anno.length-1)
			{
				bw.write("</annotation>");
			}
		}
		
		bw.close();
	}
	public static void ToHGVs_BioC_original(String InputFile,String OutputFile) throws IOException, XMLStreamException
	{
		BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
		String line="";
		String STR="";
		while ((line = br.readLine()) != null)  
		{
			STR=STR+line;
		}
		br.close();
		BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile), "UTF-8"));
		Pattern patt = Pattern.compile("^(.*?<annotation.*?>)(.+?)(</annotation>.+)$");
		Matcher mat = patt.matcher(STR);
		while(mat.find())
		{
			String STR_pre=mat.group(1);
			String annotation=mat.group(2);
			String STR_post=mat.group(3);
			bw.write(STR_pre);
			if(annotation.matches(".*<infon.*?>(Mutation|ProteinMutation|DNAMutation|SNP|Variation)</infon>.*"))
			{
				Pattern patt_id = Pattern.compile("^(.*<infon key[ ]*=[ ]*[\"\'](Identifier|tmVar|identifier|Mutation|Variation)[\"\'][ ]*>)(.+?)(</infon>.*)$");
				Matcher mat_id = patt_id.matcher(annotation);
				if(mat_id.find())
				{
					String pre=mat_id.group(1);
					String ID=mat_id.group(3);
					String post=mat_id.group(4);
					
					String ID_HGVs="";
					String VariationInformation="";
					Pattern ptmp = Pattern.compile("([^\\;]+)(;.+)$");
					Matcher mtmp = ptmp.matcher(ID);
					if(mtmp.find())
					{
						ID=mtmp.group(1);
						VariationInformation=mtmp.group(2);
					}
					String component[]=ID.split("\\|",-1);
					if(component[0].equals("p"))
					{
						if(component[1].equals("SUB") && component.length>=6)
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4];
						}
						else if(component[1].equals("INS") && component.length>=4) //"c.104insT"	--> "c|INS|104|T"
						{
							ID_HGVs=component[0]+"."+component[2]+"ins"+component[3];
						}
						else if(component[1].equals("DEL") && component.length>=4) //"c.104delT"	--> "c|DEL|104|T"
						{
							ID_HGVs=component[0]+"."+component[2]+"del"+component[3];
						}
						else if(component[1].equals("INDEL") && component.length>=4) //"c.2153_2155delinsTCCTGGTTTA"	-->	"c|INDEL|2153_2155|TCCTGGTTTA"
						{
							ID_HGVs=component[0]+"."+component[2]+"delins"+component[3];
						}
						else if(component[1].equals("DUP") && component.length>=4) //"c.1285-1301dup"	--> "c|DUP|1285_1301||"
						{
							ID_HGVs=component[0]+"."+component[2]+"dup"+component[3];
						}
						else if(component[1].equals("FS") && component.length>=6) //"p.Val35AlafsX25"	-->	"p|FS|V|35|A|25"
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
					}
					else if(component[0].equals("c") || component[0].equals("g"))
					{
						if(component[1].equals("SUB") && component.length>=5)
						{
							ID_HGVs=component[0]+"."+component[3]+component[2]+">"+component[4];
						}
						else if(component[1].equals("INS") && component.length>=4)
						{
							ID_HGVs=component[0]+"."+component[2]+"ins"+component[3];
						}
						else if(component[1].equals("DEL") && component.length>=4)
						{
							ID_HGVs=component[0]+"."+component[2]+"del"+component[3];
						}
						else if(component[1].equals("INDEL") && component.length>=4)
						{
							ID_HGVs=component[0]+"."+component[2]+"delins"+component[3];
						}
						else if(component[1].equals("DUP") && component.length>=4)
						{
							ID_HGVs=component[0]+"."+component[2]+"dup"+component[3];
						}
						else if(component[1].equals("FS") && component.length>=6)
						{
							ID_HGVs=component[0]+"."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
					}
					else if(component[0].equals(""))
					{
						if(component[1].equals("SUB") && component.length>=5)
						{
							ID_HGVs="c."+component[3]+component[2]+">"+component[4];
						}
						else if(component[1].equals("INS") && component.length>=4)
						{
							ID_HGVs="c."+component[2]+"ins"+component[3];
						}
						else if(component[1].equals("DEL") && component.length>=4)
						{
							ID_HGVs="c."+component[2]+"del"+component[3];
						}
						else if(component[1].equals("INDEL") && component.length>=4)
						{
							ID_HGVs="c."+component[2]+"delins"+component[3];
						}
						else if(component[1].equals("DUP") && component.length>=4)
						{
							ID_HGVs="c."+component[2]+"dup"+component[3];
						}
						else if(component[1].equals("FS") && component.length>=6)
						{
							ID_HGVs="p."+component[2]+component[3]+component[4]+"fsX"+component[5];
						}
					}
					if(ID_HGVs.equals(""))
					{
						Pattern patt_text = Pattern.compile("<text>(.+?)</text>");
						Matcher mat_text = patt_text.matcher(annotation);
						if(mat_text.find())
						{
							ID_HGVs=mat_text.group(1);
						}
						else
						{
							ID_HGVs=ID;
						}
						ID_HGVs=ID_HGVs.replaceAll("[^\\~\\!\\@\\#\\$\\%\\^\\&\\*\\(\\)\\_\\+\\{\\}\\|\\:\"\\<\\>\\?\\`\\-\\=\\[\\]\\;\\'\\,\\.\\/\\r\\n0-9a-zA-Z ]","");
					}
					bw.write(pre);
					bw.write(ID_HGVs+VariationInformation);
					bw.write(post);
				}
				else
				{
					bw.write(annotation);
				}
			}
			else
			{
				bw.write(annotation);
			}
			STR=STR_post;
			mat = patt.matcher(STR);
		}
		bw.write(STR);	
		bw.close();
	}
	public static void ToPostMEData(String InputFile,String OutputFile) throws IOException, XMLStreamException
	{
		try
		{
			//Parse identifier (components)
			Pattern Pattern_Component_1 = Pattern.compile("^([^|]*)\\|([^|]*)\\|([^|]*)\\|([^|]*)\\|(fs[^|]*)\\|([^|]*)$");
			Pattern Pattern_Component_1_1 = Pattern.compile("^([^|]*)\\|([^|]*(ins|del|Del|dup|-)[^|]*)\\|([^|]*)\\|([^|]*)\\|(fs[^|]*)$"); //append for p.G352fsdelG	p|del|352|G,G|fs
			Pattern Pattern_Component_2 = Pattern.compile("^([^|]*)\\|([^|]*)\\|([^|]*)\\|([^|]*)\\|(fs[^|]*)$");
			Pattern Pattern_Component_3 = Pattern.compile("^([^|]*)\\|([^|]*(ins|del|Del|dup|-|insertion|deletion|insertion|deletion|deletion\\/insertion|insertion\\/deletion|indel|delins|duplication|lack|lacked|copy|lose|losing|lacking|inserted|deleted|duplicated|insert|delete|duplicate|repeat|repeated)[^|]*)\\|([^|]*)\\|([^|]*)$");
			Pattern Pattern_Component_4 = Pattern.compile("^([^|]*)\\|([^|]*)\\|([^|]*)\\|([^|]*)$");
			Pattern Pattern_Component_5 = Pattern.compile("^([^|]*)\\|([^|]*)\\|([^|]*)\\|([^|]*)\\|([^|]*)$");
			Pattern Pattern_Component_6 = Pattern.compile("^((\\[rs\\]|[RrSs][Ss]|reference SNP no[.] )[0-9][0-9][0-9]+)$");
			
			HashMap<String,String> mention_hash = new HashMap<String,String>();
			BufferedReader inputfile = new BufferedReader(new InputStreamReader(new FileInputStream(InputFile), "UTF-8"));
			String line="";
			while ((line = inputfile.readLine()) != null)  
			{
				mention_hash.put(line, "");
			}
			inputfile.close();
			
			BufferedWriter mentionlistbw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile+".ml"), "UTF-8")); // .ml
			BufferedWriter mentiondata = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFile+".data"), "UTF-8")); // .location
			for(String mention : mention_hash.keySet() )
			{
				HashMap<Integer, String> character_hash = new HashMap<Integer, String>();
				
				int start=0;
				int last=mention.length();
				for(int s=start;s<last;s++)
				{
					character_hash.put(s,"I");
				}
				
	
				mentionlistbw.write(mention+"\n");
				mentiondata.write("I I I I I I I I I I I I I I I I I I\n");
				
				String mention_tmp=mention;
				String mention_org=mention;
				mention_tmp = mention_tmp.replaceAll("([0-9])([A-Za-z])", "$1 $2");
				mention_tmp = mention_tmp.replaceAll("([A-Za-z])([0-9])", "$1 $2");
				mention_tmp = mention_tmp.replaceAll("([A-Z])([a-z])", "$1 $2");
				mention_tmp = mention_tmp.replaceAll("([a-z])([A-Z])", "$1 $2");
				mention_tmp = mention_tmp.replaceAll("(.+)fs", "$1 fs");
				mention_tmp = mention_tmp.replaceAll("fs(.+)", "fs $1");
				mention_tmp = mention_tmp.replaceAll("[ ]+", " ");
				String regex="\\s+|(?=\\p{Punct})|(?<=\\p{Punct})";
				String Tokens[]=mention_tmp.split(regex);
				
				start=0;
				last=0;
				
				for(int i=0;i<Tokens.length;i++)
				{
					if(Tokens[i].length()>0)
					{
						String tkni=Tokens[i].replaceAll("([\\{\\}\\[\\]\\+\\-\\(\\)\\*\\?\\/\\\\])", "\\\\$1");
						Pattern Pcn = Pattern.compile("^([ ]*)("+tkni+")(.*)$");
						Matcher mPcn = Pcn.matcher(mention_org);
		    			if(mPcn.find())
						{
		    				last=last+mPcn.group(1).length();
		    				mention_org=mPcn.group(3);
		    			}
						start=last+1;
						last=start+Tokens[i].length()-1;
					
						//Number of Numbers [0-9]
						String Num_num="";
						String tmp=Tokens[i];
						tmp=tmp.replaceAll("[^0-9]","");
						if(tmp.length()>3){Num_num="N:4+";}else{Num_num="N:"+ tmp.length();}
						
						//Number of Uppercase [A-Z]
						String Num_Uc="";
						tmp=Tokens[i];
						tmp=tmp.replaceAll("[^A-Z]","");
						if(tmp.length()>3){Num_Uc="U:4+";}else{Num_Uc="U:"+ tmp.length();}
						
						//Number of Lowercase [a-z]
						String Num_Lc="";
						tmp=Tokens[i];
						tmp=tmp.replaceAll("[^a-z]","");
						if(tmp.length()>3){Num_Lc="L:4+";}else{Num_Lc="L:"+ tmp.length();}
						
						//Number of ALL char
						String Num_All="";
						if(Tokens[i].length()>3){Num_All="A:4+";}else{Num_All="A:"+ Tokens[i].length();}
						
						//specific character (;:,.->+_)
						String SpecificC="";
						tmp=Tokens[i];
						
						if(Tokens[i].equals(";") || Tokens[i].equals(":") || Tokens[i].equals(",") || Tokens[i].equals(".") || Tokens[i].equals("-") || Tokens[i].equals(">") || Tokens[i].equals("+") || Tokens[i].equals("_"))
						{
							SpecificC="-SpecificC1-";
						}
						else if(Tokens[i].equals("(") || Tokens[i].equals(")"))
						{
							SpecificC="-SpecificC2-";
						}
						else if(Tokens[i].equals("{") || Tokens[i].equals("}"))
						{
							SpecificC="-SpecificC3-";
						}
						else if(Tokens[i].equals("[") || Tokens[i].equals("]"))
						{
							SpecificC="-SpecificC4-";
						}
						else if(Tokens[i].equals("\\") || Tokens[i].equals("/"))
						{
							SpecificC="-SpecificC5-";
						}
						else
						{
							SpecificC="__nil__";
						}
						
						//mutation level
						String Mlevel="";
						if(Tokens[i].equals("p")){Mlevel="-ProteinLevel-";}
						else if(Tokens[i].matches("^[cgmr]$")){Mlevel="-DNALevel-";}
						else{Mlevel="__nil__";}
						
						//mutation type
						String Mtype="";
						String tkn=Tokens[i].toLowerCase();
						String last2_tkn="";
						String last_tkn="";
						String next_tkn="";
						String next2_tkn="";
						if(i>1){last2_tkn=Tokens[i-2];}
						if(i>0){last_tkn=Tokens[i-1];}
						if(Tokens.length>1 && i<Tokens.length-1){next_tkn=Tokens[i+1];}
						if(Tokens.length>2 && i<Tokens.length-2){next2_tkn=Tokens[i+2];}
						
						if(tkn.toLowerCase().matches("^(insert(ion|ed|ing|)|duplicat(ion|e|ed|ing)|delet(ion|e|ed|ing)|frameshift|missense|lack(|ed|ing)|los(e|ing|ed)|copy|repeat(|ed)|inversion)$")) {Mtype="-Mtype- -MtypeFull-";}
						else if(tkn.matches("^(nsert(ion|ed|ing|)|uplicat(ion|e|ed|ing)|elet(ion|e|ed|ing)|rameshift|issense|ack(|ed|ing)|os(e|ing|ed)|opy|epeat(|ed)|nversion)$")) {Mtype="-Mtype- -MtypeFull_suffix-";}
						else if(tkn.matches("^(del|ins|delins|indel|dup|inv)$")) {Mtype="-Mtype- -MtypeTri-";}
						else if(tkn.matches("^(start[a-z]*|found|identif[a-z]+|substit[a-z]*|lead[a-z]*|exchang[a-z]*|chang[a-z]*|mutant[a-z]*|mutate[a-z]*|devia[a-z]*|modif[a-z]*|alter[a-z]*|switch[a-z]*|variat[a-z]*|instead[a-z]*|replac[a-z]*|in place|convert[a-z]*|becom[a-z]*|transition|transversion)$")) {Mtype="-SurroundingWord- -CausingVerb-";}
						else if(tkn.matches("^(caus(e|es|ing)|lead(|s|ing|ed)|encod(e|es|ing|ed)|result(|s|ing|ed)|produc(e|es|ing|ed)|chang(e|es|ing|ed)|covert(|s|ing|ed)|correspond(|s|ing|ed)|predict(|s|ing|ed)|cod(e|es|ing|ed)|concordanc(e|es|ing|ed)|concordant|consist(|s|ing|ed)|encod(e|es|ing|ed)|represent(|s|ing|ed)|led|responsible|denot(e|es|ing|ed)|designat(e|es|ing|ed)|introduc(e|es|ing|ed)|characteriz(e|es|ing|ed)|bring|involv(e|es|ing|ed)|implicat(e|es|ing|ed)|indicat(e|es|ing|ed)|express(|s|ing|ed)|behav(e|es|ing|ed)|suggest(|s|ing|ed)|impl(y|ies|ed|ying)|presum(e|es|ing|ed))$")) {Mtype="-SurroundingWord- -CausingVerb-";}
						else if(tkn.matches("^(polymorphic|site|point|premature|replacement|replac(e|es|ed|ing)|substitution(s|)|polar|charged|amphipathic|hydrophobic|amino|acid(s|)|nucleotide(s|)|mutation(s|)|position(s|)|posi|pos|islet|liver|base|pair(s|)|bp|bps|bp|residue(s|)|radical|codon|aa|nt|alpha|beta|gamma|ezta|theta|delta|tetranucleotide|polymorphism|terminal)$")) {Mtype="-SurroundingWord- -SurroundingWord2-";}
						else if(tkn.matches("^((has|have|had) been|is|are|was|were)$")) {Mtype="-SurroundingWord- -BeVerb-";}
						else if(Tokens[i].matches("^(a|an|the|)$")) {Mtype="-SurroundingWord- -Article-";}
						else if(Tokens[i].matches("^(which|where|what|that)$")) {Mtype="-SurroundingWord- -RelativePronouns-";}
						else if(Tokens[i].matches("^(in|to|into|for|of|by|with|at|locat(e|ed|es)|among|between|through|rather|than|either)$")) {Mtype="-SurroundingWord- -Preposition-";}
						else if(tkn.equals("/") && last_tkn.matches("(ins|del)") && next_tkn.toLowerCase().matches("(ins|del)")) {Mtype="-Mtype- -MtypeTri-";}
						else if((last2_tkn.toLowerCase().equals("/") && last_tkn.toLowerCase().equals("\\")) || (next_tkn.toLowerCase().equals("/") && next2_tkn.toLowerCase().equals("\\"))) {Mtype="-Mtype- -MtypeTri-";}
						else {Mtype="__nil__ __nil__";}
						
						//DNA symbols
						String DNASym="";
						if(tkn.matches("^(adenine|guanine|thymine|cytosine)$")){DNASym="-DNASym- -DNASymFull-";}
						else if(tkn.matches("^(denine|uanine|hymine|ytosine)$")){DNASym="-DNASym- -DNASymFull_suffix-";}
						else if(Tokens[i].matches("^[ATCGU]+$")){DNASym="-DNASym- -DNASymChar-";}
						else {DNASym="__nil__ __nil__";}
						
						//Protein symbols
						String ProteinSym="";
						if(tkn.matches("^(glutamine|glutamic|leucine|valine|isoleucine|lysine|alanine|glycine|aspartate|methionine|threonine|histidine|aspartic|asparticacid|arginine|asparagine|tryptophan|proline|phenylalanine|cysteine|serine|glutamate|tyrosine|stop|frameshift)$")){ProteinSym="-ProteinSym- -ProteinSymFull-";}
						else if(tkn.matches("^(lutamine|lutamic|eucine|aline|soleucine|ysine|lanine|lycine|spartate|ethionine|hreonine|istidine|spartic|sparticacid|rginine|sparagine|ryptophan|roline|henylalanine|ysteine|erine|lutamate|yrosine|top|rameshift)$")){ProteinSym="-ProteinSym- -ProteinSymFull_suffix-";}
						else if(tkn.matches("^(cys|ile|ser|gln|met|asn|pro|lys|asp|thr|phe|ala|gly|his|leu|arg|trp|val|glu|tyr)$")){ProteinSym="-ProteinSym- -ProteinSymTri-";}
						else if(tkn.matches("^(ys|le|er|ln|et|sn|ro|ys|sp|hr|phe|la|ly|is|eu|rg|rp|al|lu|yr)$")){ProteinSym="-ProteinSym- -ProteinSymTri_suffix-";}
						else if(Tokens[i].matches("^[CISQMNPKDTFAGHLRWVEYX]$") && !next_tkn.toLowerCase().matches("^[ylsrhpiera]")) {ProteinSym="-ProteinSym- -ProteinSymChar-";}
						else if(Tokens[i].matches("^[CISGMPLTHAVF]$") && next_tkn.toLowerCase().matches("^[ylsrhpiera]")) {ProteinSym="-ProteinSym- -ProteinSymChar-";}
						else {ProteinSym="__nil__ __nil__";}
						
						//IVS/EX
						String IVSEX="";
						if(tkn.matches("^(ivs|ex)$")){IVSEX="-IVSEX-";}
						else if(Tokens[i].equals("E") && last_tkn.equals("x")){IVSEX="-IVSEX-";}
						else if(last_tkn.equals("E") && Tokens[i].equals("x")){IVSEX="-IVSEX-";}
						else {IVSEX="__nil__";}
						
						//FSX feature
						String FSXfeature="";
						if(tkn.matches("^(fs|fsx|x|\\*)$")){FSXfeature="-FSX-";}
						else if(last_tkn.toLowerCase().equals("s") && tkn.equals("x")){FSXfeature="-FSX-";}
						else {FSXfeature="__nil__";}
						
						//position type
						String PositionType="";
						if(tkn.matches("^(nucleotide|codon|amino|acid|position|bp|b|base|pair)$")){PositionType="-PositionType-";}
						else if(tkn.matches("^(single|one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+)$")){PositionType="-PositionNum-";}
						else {PositionType="__nil__";}
						
						//sequence location
						String SeqLocat="";
						if(tkn.matches("^(intron|exon|promoter|utr)$")){SeqLocat="-SeqLocat-";}
						else {SeqLocat="__nil__";}
						
						//RS
						String RScode="";
						if(tkn.equals("rs")){RScode="-RScode-";}
						else {RScode="__nil__";}
						
						mentiondata.write(Tokens[i]+" "+Num_num+" "+Num_Uc+" "+Num_Lc+" "+Num_All+" "+SpecificC+" "+Mlevel+" "+Mtype+" "+DNASym+" "+ProteinSym+" "+IVSEX+" "+FSXfeature+" "+PositionType+" "+SeqLocat+" "+RScode+"\n");
					}
				}
				mentiondata.write("\n");
			}
			mentionlistbw.close();
			mentiondata.close();
		}
		catch(IOException e1){ System.out.println("[toPostMEData]: "+e1+" Input file is not exist.");}
	}
	
	public static void ToPostMEoutput(String FilenamePostMEdata,String FilenamePostMEoutput) throws IOException
	{
		/* 
		 * Recognizing components
		 */
		Runtime runtime = Runtime.getRuntime();
	    String OS=System.getProperty("os.name").toLowerCase();
		String cmd="";
	    if(OS.contains("windows"))
	    {
	    	cmd ="CRF/crf_test -m CRF/ComponentExtraction.Model -o "+FilenamePostMEoutput+" "+FilenamePostMEdata;
	    }
	    else //if(OS.contains("nux")||OS.contains("nix"))
	    {
	    	cmd ="./CRF/crf_test -m CRF/ComponentExtraction.Model -o "+FilenamePostMEoutput+" "+FilenamePostMEdata;
	    }
	    
	    try {
	    	File f = new File(FilenamePostMEoutput);
	        BufferedWriter fr = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(f), "UTF-8"));
	    	Process process = runtime.exec(cmd);
	    	InputStream is = process.getInputStream();
	    	InputStreamReader isr = new InputStreamReader(is);
	    	BufferedReader br = new BufferedReader(isr);
	    	String line="";
		    while ( (line = br.readLine()) != null) 
		    {
		    	fr.write(line);
		    	fr.newLine();
		        fr.flush();
		    }
		    is.close();
		    isr.close();
		    br.close();
		    fr.close();
	    }
	    catch (IOException e) {
	    	System.out.println(e);
	    	runtime.exit(0);
	    }
	}
	
	public static void TotmVArFormList(String inputfile,String FilenamePostMEoutput,String FilenamePostMEml,String outputfile) throws IOException
	{
		ArrayList<String> mentionlist = new ArrayList<String>(); 
		ArrayList<String> identifierlist = new ArrayList<String>(); 
		ArrayList<String> typelist = new ArrayList<String>(); 
		BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(FilenamePostMEml), "UTF-8"));
		int count=0;
		HashMap<Integer,Integer> boundary_hash = new HashMap<Integer,Integer>();
		HashMap<Integer,String> WMstate_hash = new HashMap<Integer,String>();
		String line;
		while ((line = br.readLine()) != null)  
		{
			String columns[]=line.split("\\t",-1);
			String line_nospace=columns[0].replaceAll(" ","");
			Pattern pat1 = Pattern.compile("(.+?)(for|inplaceof|insteadof|mutantof|mutantsof|ratherthan|ratherthan|replacementof|replacementsof|replaces|replacing|residueatposition|residuefor|residueinplaceof|residueinsteadof|substitutioat|substitutionfor|substitutionof|substitutionsat|substitutionsfor|substitutionsof|substitutedfor|toreplace)(.+)$");
			Matcher mat1 = pat1.matcher(line_nospace.toLowerCase());
			Pattern pat2 = Pattern.compile("^(.+?)(>|to|into|of|by|with|at)(.+)$");
			Matcher mat2 = pat2.matcher(line_nospace.toLowerCase());
			
			if(mat1.find())
			{
				boundary_hash.put(count,mat1.group(1).length());
				WMstate_hash.put(count,"Backward");
			}
			else if(mat2.find())
			{
				boundary_hash.put(count,mat2.group(1).length());
				WMstate_hash.put(count,"Forward");
			}
			mentionlist.add(columns[0]);
			if(columns.length==2)
			{
				typelist.add(columns[1]);
			}
			else
			{
				typelist.add("DNAMutation");
			}
			count++;
		}
		br.close();
		
		HashMap<String,String> component_hash = new HashMap<String,String>();
		component_hash.put("A", ""); //type
		component_hash.put("T", ""); //Method
		component_hash.put("P", ""); //Position
		component_hash.put("W", ""); //Wide type
		component_hash.put("M", ""); //Mutant
		component_hash.put("F", ""); //frame shift
		component_hash.put("S", ""); //frame shift position
		component_hash.put("D", ""); //
		component_hash.put("I", ""); //Inside
		component_hash.put("R", ""); //RS number
		
		BufferedReader PostMEfile = new BufferedReader(new InputStreamReader(new FileInputStream(FilenamePostMEoutput), "UTF-8"));
		String prestate="";
		count=0;
		int start_count=0;
		boolean codon_exist=false;
		HashMap<Integer,String> filteringNum_hash = new HashMap<Integer,String>();
		
		while ((line = PostMEfile.readLine()) != null)  
		{
			String outputs[]=line.split("\\t",-1);
			
			/*
			 * recognize status and mention
			 */
			if(outputs.length<=1)
			{
				//System.out.println(component_hash.get("W")+"\t"+component_hash.get("P")+"\t"+component_hash.get("M"));
				/*
				 *  Translate : nametothree | threetone | etc
				 */
				component_hash.put("W",component_hash.get("W").toUpperCase());
				component_hash.put("M",component_hash.get("M").toUpperCase());
				component_hash.put("P",component_hash.get("P").toUpperCase());
				boolean translate=false;
				boolean NotAaminoacid=false;
				boolean exchange_nu=false;
				//M
				HashMap<String,String> component_avoidrepeat = new HashMap<String,String>();
				String components[]=component_hash.get("M").split(",");
				component_hash.put("M","");
				String component="";
				for(int i=0;i<components.length;i++)
				{
					if(nametothree.containsKey(components[i]))
					{
						component=nametothree.get(components[i]);
						translate=true;
					}
					else if(NTtoATCG.containsKey(components[i]))
					{
						component=NTtoATCG.get(components[i]);
						NotAaminoacid=true;
					}
					else if(threetone_nu.containsKey(components[i]) && NotAaminoacid==false && translate==false) //&& (component_hash.get("P").matches("(.*CODON.*|)") || codon_exist == true) 
					{
						component=threetone_nu.get(components[i]);
						exchange_nu=true;
					}
					else
					{
						component=components[i];
					}
					
					if(component_hash.get("M").equals(""))
					{
						component_hash.put("M",component);
					}
					else
					{
						if(!component_avoidrepeat.containsKey(component))
						{
							component_hash.put("M",component_hash.get("M")+","+component);
						}
					}
					component_avoidrepeat.put(component,"");
				}
				
				component_avoidrepeat = new HashMap<String,String>();
				String components2[]=component_hash.get("M").split(",");
				component_hash.put("M","");
				component="";
				for(int i=0;i<components2.length;i++)
				{
					if(threetone.containsKey(components2[i]))
					{
						component=threetone.get(components2[i]);
						translate=true;
					}
					else if(NTtoATCG.containsKey(components2[i]))
					{
						component=NTtoATCG.get(components2[i]);
						NotAaminoacid=true;
					}
					else if(threetone_nu.containsKey(components2[i]) && NotAaminoacid==false && translate==false) //&& (component_hash.get("P").matches("(.*CODON.*|)") || codon_exist == true) 
					{
						component=threetone_nu.get(components2[i]);
						exchange_nu=true;
					}
					else if(components2[i].length()>1)
					{
						NotAaminoacid=false;
						component=components2[i];
					}
					else
					{
						component=components2[i];
					}	
					if(component_hash.get("M").equals(""))
					{
						component_hash.put("M",component);
					}
					else
					{
						if(!component_avoidrepeat.containsKey(component))
						{
							component_hash.put("M",component_hash.get("M")+","+component);
						}
					}
					component_avoidrepeat.put(component,"");
				}
				
				//W
				component_avoidrepeat = new HashMap<String,String>();
				String components3[]=component_hash.get("W").split(",");
				component_hash.put("W","");
				component="";
				for(int i=0;i<components3.length;i++)
				{
					if(nametothree.containsKey(components3[i]))
					{
						component=nametothree.get(components3[i]);
						translate=true;
					}
					else if(NTtoATCG.containsKey(components3[i]))
					{
						component=NTtoATCG.get(components3[i]);
						NotAaminoacid=true;
					}
					else if(threetone_nu.containsKey(components3[i]) && NotAaminoacid==false && translate==false) //&& (component_hash.get("P").matches("(.*CODON.*|)") || codon_exist == true) 
					{
						component=threetone_nu.get(components3[i]);
						exchange_nu=true;
					}
					else
					{
						component=components3[i];
					}	
					if(component_hash.get("W").equals(""))
					{
						component_hash.put("W",component);
					}
					else
					{
						if(!component_avoidrepeat.containsKey(component))
						{
							component_hash.put("W",component_hash.get("W")+","+component);
						}
					}
					component_avoidrepeat.put(component,"");
				}
				
				component_avoidrepeat = new HashMap<String,String>();
				String components4[]=component_hash.get("W").split(",");
				component_hash.put("W","");
				component="";
				for(int i=0;i<components4.length;i++)
				{
					if(threetone.containsKey(components4[i]))
					{
						component=threetone.get(components4[i]);
						translate=true;
					}
					else if(NTtoATCG.containsKey(components4[i]))
					{
						component=NTtoATCG.get(components4[i]);
						NotAaminoacid=true;
					}
					else if(threetone_nu.containsKey(components4[i]) && NotAaminoacid==false && translate==false) //&& (component_hash.get("P").matches("(.*CODON.*|)") || codon_exist == true) 
					{
						component=threetone_nu.get(components4[i]);
						exchange_nu=true;
					}
					else if(components4[i].length()>1)
					{
						NotAaminoacid=false;
						component=components4[i];
					}
					else
					{
						component=components4[i];
					}	
					if(component_hash.get("W").equals(""))
					{
						component_hash.put("W",component);
					}
					else
					{
						if(!component_avoidrepeat.containsKey(component))
						{
							component_hash.put("W",component_hash.get("W")+","+component);
						}
					}
					component_avoidrepeat.put(component,"");
				}
				//System.out.println(component_hash.get("W")+"\t"+component_hash.get("P")+"\t"+component_hash.get("M")+"\n");
				
				//W/M - 2
				if(component_hash.get("W").matches(",") && (component_hash.get("M").equals("") && component_hash.get("T").equals("")))
				{
					String spl[]=component_hash.get("W").split("-");
					component_hash.put("W",spl[0]);
					component_hash.put("M",spl[1]);
				}
				if(component_hash.get("M").matches(",") && (component_hash.get("W").equals("") && component_hash.get("T").equals("")))
				{
					String spl[]=component_hash.get("M").split("-");
					component_hash.put("W",spl[0]);
					component_hash.put("M",spl[1]);
				}
				
				if(component_hash.get("M").equals("CODON")) // TGA stop codon at nucleotides 766 to 768	ProteinMutation	p|SUB|X|766_768|CODON
				{
					component_hash.put("M","");
				}
				
				//A
				Pattern pap = Pattern.compile("[+-][0-9]");
				Matcher mp = pap.matcher(component_hash.get("P"));
				component_hash.put("A",component_hash.get("A").toLowerCase());
				if(component_hash.get("A").equals("") && component_hash.get("P").matches("[\\+]*[0-9]+") && (component_hash.get("P").matches("[\\-\\+]{0,1}[0-9]{1,8}")  && component_hash.get("W").matches("[ATCG]")  && component_hash.get("M").matches("[ATCG]") && Integer.parseInt(component_hash.get("P"))>3000)) 
				{
					component_hash.put("A","g");
				}
				else if(component_hash.get("A").equals("cdna"))
				{
					component_hash.put("A","c");
				}
				else if(component_hash.get("A").equals("") && mp.find() && !typelist.get(count).equals("ProteinMutation"))
				{
					component_hash.put("A","c");
				}
				else if(component_hash.get("W").matches("^[ATCG]*$") && component_hash.get("M").matches("^[ATCG]*$") && translate==false && component_hash.get("A").equals(""))
				{
					component_hash.put("A","c");
				}
				
				//F
				if(component_hash.get("F").equals("*"))
				{
					component_hash.put("F","X");
				}
				
				//R
				component_hash.put("R",component_hash.get("R").toLowerCase());
				component_hash.put("R",component_hash.get("R").replaceAll("[\\[\\]]", ""));
				
				//P
				Pattern pat = Pattern.compile("^([0-9]+)[^0-9,]+([0-9]{1,8})$");
				Matcher mat = pat.matcher(component_hash.get("P"));
				if(mat.find()) //Title|Abstract
	        	{
					if(Integer.parseInt(mat.group(1))<Integer.parseInt(mat.group(2)))
					{
						component_hash.put("P",mat.group(1)+"_"+mat.group(2));
					}
	        	}
				component_hash.put("P",component_hash.get("P").replaceAll("[-\\[]+$", ""));
				component_hash.put("P",component_hash.get("P").replaceAll("^(POSITION|NUCLEOTIDE|BASE|PAIR[S]*|NT|AA||:)", ""));
				component_hash.put("P",component_hash.get("P").replaceAll("^(POSITION|NUCLEOTIDE|BASE|PAIR[S]*|NT|AA||:)", ""));
				if(typelist.get(count).equals("ProteinMutation") || typelist.get(count).equals("ProteinAllele"))
				{
					component_hash.put("P",component_hash.get("P").replaceAll("^CODON", ""));	
				}
				else if(typelist.get(count).equals("DNAMutation")) 
				{
					if(codon_exist==true)
					{	
						//add codon back
						if(component_hash.get("P").matches("[0-9]+"))
						{
							component_hash.put("P","CODON"+component_hash.get("P"));
						}
						
						//if(component_hash.get("W").matches("[ATCGUatcgu]") && component_hash.get("M").matches("[ATCGUatcgu]"))
						//{
						//	//codon position * 3
						//	//codon position * 3 - 1
						//	//codon position * 3 - 2
						//	String position_wo_codon=component_hash.get("P").replaceAll("^CODON", "");
						//	int position1=Integer.parseInt(position_wo_codon)*3;
						//	int position2=position1-1;
						//	int position3=position1-2;
						//	component_hash.put("P",position1+","+position2+","+position3);
						//}
					}
				}
				
				//T
				component_hash.put("T",component_hash.get("T").toUpperCase());
				
				//refine the variant types
				for(String original_type : VariantType_hash.keySet())
				{
					String formal_type=VariantType_hash.get(original_type);
					if(component_hash.get("T").equals(original_type))
					{
						component_hash.put("T",formal_type);
						break;
					}
				}
				
				if(component_hash.get("T").matches(".*INS.*DEL.*")) {component_hash.put("T","INDEL"); translate=false;}
				else if(component_hash.get("T").matches(".*DEL.*INS.*")) {component_hash.put("T","INDEL"); translate=false;}
				else if(component_hash.get("T").matches(".*DUPLICATION.*")) {component_hash.put("T","DUP"); translate=false;} //multiple types : 15148206	778	859	27 bp duplication was found inserted in the 2B domain at nucleotide position 1222
				else if(component_hash.get("T").matches(".*INSERTION.*")) {component_hash.put("T","INS"); translate=false;} //multiple types
				else if(component_hash.get("T").matches(".*DELETION.*")) {component_hash.put("T","DEL"); translate=false;} //multiple types
				else if(component_hash.get("T").matches(".*INDEL.*")) {component_hash.put("T","INDEL"); translate=false;} //multiple types
				
				if(component_hash.get("T").matches("(DEL|INS|DUP|INDEL)") && !(component_hash.get("W").equals("")) && component_hash.get("M").equals(""))
				{
					component_hash.put("M",component_hash.get("W"));
				}
				else if(component_hash.get("M").matches("(DEL|INS|DUP|INDEL)"))
				{
					component_hash.put("T",component_hash.get("M"));
					component_hash.put("M","");
				}
				else if(component_hash.get("W").matches("(DEL|INS|DUP|INDEL)"))
				{
					component_hash.put("T",component_hash.get("W"));
					component_hash.put("W","");
				}
				else if(!component_hash.get("D").equals(""))
				{
					component_hash.put("T","DUP");
				}
				
				if(Number_word2digit.containsKey(component_hash.get("M")))
				{
					component_hash.put("M",Number_word2digit.get(component_hash.get("M")));
				}

				//System.out.println(component_hash.get("T")+"\t"+component_hash.get("W")+"\t"+component_hash.get("P")+"\t"+component_hash.get("M"));
				
				String type="";
				if(exchange_nu==true)
				{
					component_hash.put("P",component_hash.get("P").replaceAll("^CODON", ""));
					component_hash.put("A","p");
					type="ProteinMutation";
				}
				
				String identifier="";
				if(component_hash.get("T").equals("DUP") && !component_hash.get("D").equals("")) //dup
				{
					identifier=component_hash.get("A")+"|"+component_hash.get("T")+"|"+component_hash.get("P")+"|"+component_hash.get("M")+"|"+component_hash.get("D");
				}
				else if(component_hash.get("T").equals("DUP")) //dup
				{
					identifier=component_hash.get("A")+"|"+component_hash.get("T")+"|"+component_hash.get("P")+"|"+component_hash.get("M")+"|";
				}
				else if(!component_hash.get("T").equals("")) //DEL|INS|INDEL
				{
					identifier=component_hash.get("A")+"|"+component_hash.get("T")+"|"+component_hash.get("P")+"|"+component_hash.get("M");
				}
				else if(!component_hash.get("F").equals("")) //FS
				{
					identifier=component_hash.get("A")+"|FS|"+component_hash.get("W")+"|"+component_hash.get("P")+"|"+component_hash.get("M")+"|"+component_hash.get("S");
					type="ProteinMutation";
				}
				else if(!component_hash.get("R").equals("")) //RS
				{
					identifier=mentionlist.get(count);
					type="SNP";
				}
				else if(mentionlist.get(count).matches("^I([RSrs][Ss][0-9].+)"))
				{
					String men=mentionlist.get(count);
					men.substring(1, men.length());
					men=men.replaceAll("[\\W-_]", men.toLowerCase());
					type="SNP";
				}
				else if(component_hash.get("W").equals("") && !component_hash.get("M").equals("")) //Allele
				{
					identifier=component_hash.get("A")+"|Allele|"+component_hash.get("M")+"|"+component_hash.get("P");
				}
				else if(component_hash.get("M").equals("") && !component_hash.get("W").equals("")) //Allele
				{
					identifier=component_hash.get("A")+"|Allele|"+component_hash.get("W")+"|"+component_hash.get("P");
				}
				else if((!component_hash.get("M").equals("")) && (!component_hash.get("W").equals("")) && component_hash.get("P").equals("")) //AcidChange
				{
					identifier=component_hash.get("A")+"|SUB|"+component_hash.get("W")+"||"+component_hash.get("M");
				}
				else
				{
					identifier=component_hash.get("A")+"|SUB|"+component_hash.get("W")+"|"+component_hash.get("P")+"|"+component_hash.get("M");
				}
				
				// filteringNum_hash
				//if(component_hash.get("M").equals(component_hash.get("W")) && (!component_hash.get("W").equals("")) && type.equals("DNAMutation")) // remove genotype
				//{
				//	filteringNum_hash.put(count, "");
				//}
				//else if(NotAaminoacid==false && type.equals("ProteinMutation")) //E 243 ASPARTATE
				//{
				//	filteringNum_hash.put(count, "");
				//}
				//else if(component_hash.get("W").matches(",") && component_hash.get("M").matches(",") && component_hash.get("P").matches("")) //T,C/T,C
				//{
				//	filteringNum_hash.put(count, "");
				//}
				//if(component_hash.get("W").equals("") && component_hash.get("M").equals("") && component_hash.get("T").equals("") && !type.equals("SNP")) //exons 5
				//{
				//	filteringNum_hash.put(count, "");
				//}
				if(mentionlist.get(count).matches("^I[RSrs][Ss]") && type.equals("SNP")) //exons 5
				{
					filteringNum_hash.put(count, "");
				}
				
				// Recognize the type of mentions: ProteinMutation | DNAMutation | SNP 
				if(type.equals(""))
				{
					if(NotAaminoacid==true)
					{
						type="DNAMutation";
						if(!component_hash.get("A").matches("[gmrn]"))
						{
							component_hash.put("A","c");
						}
					}
					else if(translate==true || exchange_nu==true)
					{
						type="ProteinMutation";
					}
					else
					{
						type="DNAMutation";
					}
					
					if(component_hash.get("P").matches("^([Ee]x|EX|[In]ntron|IVS|[Ii]vs)"))
					{
						type="DNAMutation";
						identifier=identifier.replaceAll("^[^|]*\\|","c|");
					}
					else if(component_hash.get("M").matches("[ISQMNPKDFHLRWVEYX]") || component_hash.get("W").matches("[ISQMNPKDFHLRWVEYX]") )
					{
						type="ProteinMutation";
						identifier=identifier.replaceAll("^[^|]*\\|","p|");
					}
					else if(component_hash.get("P").matches(".*[\\+\\-\\?].*"))
					{
						type="DNAMutation";
						identifier=identifier.replaceAll("^[^|]*\\|","c|");
					}
					else if(type.equals(""))
					{
						type="ProteinMutation";
					}
					
					if(!component_hash.get("A").equals("") &&
					   (
					   component_hash.get("A").toLowerCase().equals("c") ||
					   component_hash.get("A").toLowerCase().equals("r") ||
					   component_hash.get("A").toLowerCase().equals("m") ||
					   component_hash.get("A").toLowerCase().equals("g")
					   )
					  )
					{
						type="DNAMutation";
						identifier=identifier.replaceAll("^[^|]*\\|",component_hash.get("A")+"|");
					}
					else if(component_hash.get("A").equals("p"))
					{
						type="ProteinMutation";
					}
				}
				
				if(type.equals("ProteinMutation"))
				{
					identifier=identifier.replaceAll("^[^|]*\\|","p|");
				}
				
				if(type.equals("ProteinMutation") && (!component_hash.get("W").equals("")) && (!component_hash.get("M").equals("")) && component_hash.get("P").equals(""))
				{
					type="ProteinAcidChange";
				}
				else if(type.equals("DNAMutation") && (!component_hash.get("W").equals("")) && (!component_hash.get("M").equals("")) && component_hash.get("P").equals(""))
				{
					type="DNAAcidChange";
				}
				//else if(type.equals("ProteinMutation") && component_hash.get("T").equals("")  && component_hash.get("A").equals("") && (!component_hash.get("W").equals("")) && component_hash.get("W").equals(component_hash.get("M")))
				//{
				//	type="ProteinAllele";
				//	identifier=component_hash.get("A")+"|Allele|"+component_hash.get("M")+"|"+component_hash.get("P");
				//}
				//else if(type.equals("DNAMutation") && component_hash.get("T").equals("") && (!component_hash.get("W").equals("")) && component_hash.get("W").equals(component_hash.get("M")))
				//{
				//	type="DNAAllele";
				//	identifier=component_hash.get("A")+"|Allele|"+component_hash.get("M")+"|"+component_hash.get("P");
				//}
				
				//System.out.println(identifier+"\t"+component_hash.get("T")+"\t"+component_hash.get("W")+"\t"+component_hash.get("P")+"\t"+component_hash.get("M"));
				
				boolean show_removed_cases=false;
				// filtering and Print out
				if( (component_hash.get("W").length() == 3 || component_hash.get("M").length() == 3) 
						&& component_hash.get("W").length() != component_hash.get("M").length()
						&& !component_hash.get("W").equals("") && !component_hash.get("M").equals("") && component_hash.get("W").indexOf(",")!=-1 && component_hash.get("M").indexOf(",")!=-1
						&& ((component_hash.get("W").indexOf("A")!=-1 && component_hash.get("W").indexOf("T")!=-1 && component_hash.get("W").indexOf("C")!=-1 && component_hash.get("W").indexOf("G")!=-1) || (component_hash.get("M").indexOf("A")!=-1 && component_hash.get("M").indexOf("T")!=-1 && component_hash.get("M").indexOf("C")!=-1 && component_hash.get("M").indexOf("G")!=-1))
						&& component_hash.get("T").equals("")
					)
				{if(show_removed_cases==true){System.out.println("filtering 1:"+mentionlist.get(count));}identifierlist.add("_Remove_");}
				else if((component_hash.get("M").matches("[ISQMNPKDFHLRWVEYX]") || component_hash.get("W").matches("[ISQMNPKDFHLRWVEYX]")) && component_hash.get("P").matches("[6-9][0-9][0-9][0-9]+")){if(show_removed_cases==true){System.out.println("filtering 2 length:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //M300000X
				else if(component_hash.get("T").equals("DUP") && component_hash.get("M").matches("") && component_hash.get("P").equals("") && !type.equals("SNP")){if(show_removed_cases==true){System.out.println("filtering 3:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //|DUP|||4]q33-->qter	del[4] q33-->qter	del4q33qter
				//else if(component_hash.get("T").equals("") && component_hash.get("M").matches("[ATCGUatcgu]") && (component_hash.get("M").equals(component_hash.get("W")))){if(show_removed_cases==true){System.out.println("filtering 4:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //T --> T
				else if(component_hash.get("P").matches("[\\-\\<\\)\\]][0-9]+") && type.equals("ProteinMutation")){if(show_removed_cases==true){System.out.println("filtering 5:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //negative protein mutation
				else if(component_hash.get("P").matches(".*>.*")){if(show_removed_cases==true){System.out.println("filtering 6:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //negative protein mutation
				else if(component_hash.get("W").matches("^[BJOUZ]") || component_hash.get("M").matches("^[BJOUZ]")){if(show_removed_cases==true){System.out.println("filtering 7:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //not a mutation
				else if(component_hash.get("T").equals("&")){if(show_removed_cases==true){System.out.println("filtering 8:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //not a mutation
				else if((!component_hash.get("T").equals("")) && component_hash.get("P").equals("")){if(show_removed_cases==true){System.out.println("filtering 8-1:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //Delta32
				else if(component_hash.get("W").equals("") && component_hash.get("M").equals("") && component_hash.get("T").equals("") && (!type.equals("SNP")) && (!component_hash.get("P").matches(".*\\?.*"))){if(show_removed_cases==true){System.out.println("filtering 9:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //not a mutation
				else if(type.equals("SNP") && identifier.matches("RS[0-9]+")){if(show_removed_cases==true){System.out.println("filtering 2-1:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //start with RS (uppercase)
				else if(type.equals("SNP") && identifier.matches("[Rr][Ss][0-9][0-9]{0,1}")){if(show_removed_cases==true){System.out.println("filtering 2-2:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //too short rs number
				else if(type.equals("SNP") && identifier.matches("[Rr][Ss]0[0-9]*")){if(show_removed_cases==true){System.out.println("filtering 2-3:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //start with 0
				else if(type.equals("SNP") && identifier.matches("[Rr][Ss][0-9]{11,}")){if(show_removed_cases==true){System.out.println("filtering 2-4:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //too long rs number; allows 10 numbers or less
				else if(type.equals("SNP") && identifier.matches("[Rr][Ss][5-9][0-9]{9,}")){if(show_removed_cases==true){System.out.println("filtering 2-5:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //too long rs number; allows 10 numbers or less
				else if(type.equals("SNP") && identifier.matches("[0-9][0-9]{0,1}[\\W\\-\\_]*delta")){if(show_removed_cases==true){System.out.println("filtering 2-6:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //0 delta
				//else if(PAM_lowerScorePair.contains(component_hash.get("M")+"\t"+component_hash.get("W"))){if(show_removed_cases==true){System.out.println("filtering 7-1:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //unlikely to occur
				//else if(component_hash.get("P").equals("") && component_hash.get("T").equals("") && (!type.equals("SNP"))){if(show_removed_cases==true){System.out.println("filtering 8-2:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //position is empty
				else if(component_hash.get("W").equals("") && component_hash.get("M").equals("") && component_hash.get("T").equals("") && (!type.equals("SNP")) && (!component_hash.get("P").contains("?"))){if(show_removed_cases==true){System.out.println("filtering 8-3:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //p.1234
				else if(component_hash.get("P").matches("[21][0-9][0-9][0-9]") && (component_hash.get("W").matches("(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)") || component_hash.get("M").matches("(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"))){if(show_removed_cases==true){System.out.println("filtering 8-4:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //May 2018The
				else if(type.equals("AcidChange") && component_hash.get("W").equals(component_hash.get("M"))){if(show_removed_cases==true){System.out.println("filtering 8-5:"+mentionlist.get(count));}identifierlist.add("_Remove_");} //Met/Met Genotype
				else if(type.matches("DNAMutation|ProteinMutation") && component_hash.get("T").equals("") && (component_hash.get("W").length() != component_hash.get("M").length()) && component_hash.get("W").length()>0 && component_hash.get("M").length()>0 && (!component_hash.get("P").matches(".*\\?.*")) && (!component_hash.get("W").matches(".*,.*")) && (!component_hash.get("M").matches(".*,.*"))){if(show_removed_cases==true){System.out.println("filtering 8-6:"+mentionlist.get(count)+"\t"+component_hash.get("W")+"\t"+component_hash.get("M"));}identifierlist.add("_Remove_");} //GUCA1A
				else
				{
					identifierlist.add(identifier);
					if(typelist.get(count).matches("DNAAllele|ProteinAllele")){}
					else
					{
						typelist.set(count,type);
					}
				}
				
				//End
				component_hash.put("A", "");
				component_hash.put("T", "");
				component_hash.put("P", "");
				component_hash.put("W", "");
				component_hash.put("M", "");
				component_hash.put("F", "");
				component_hash.put("S", "");
				component_hash.put("D", "");
				component_hash.put("I", "");
				component_hash.put("R", "");
				count++;
				start_count=0;
			}
			else if(outputs[1].equals("I"))
			{
				//Start
				codon_exist=false;
			}
			else if(outputs[outputs.length-1].matches("[ATPWMFSDIR]"))
			{
				if(WMstate_hash.containsKey(count) && WMstate_hash.get(count).equals("Forward"))
				{
					if(start_count<boundary_hash.get(count) && outputs[outputs.length-1].equals("M"))
					{
						outputs[outputs.length-1]="W";
					}
					else if(start_count>boundary_hash.get(count) && outputs[outputs.length-1].equals("W"))
					{
						outputs[outputs.length-1]="M";
					}
				}
				else if(WMstate_hash.containsKey(count) && WMstate_hash.get(count).equals("Backward"))
				{
					if(start_count<boundary_hash.get(count) && outputs[outputs.length-1].equals("W"))
					{
						outputs[outputs.length-1]="M";
					}
					else if(start_count>boundary_hash.get(count) && outputs[outputs.length-1].equals("M"))
					{
						outputs[outputs.length-1]="W";
					}
				}
				String state=outputs[outputs.length-1];	
				String tkn=outputs[0];
				
				if(!component_hash.get(state).equals("") && !state.equals(prestate)) //add "," if the words are not together
				{
					component_hash.put(state, component_hash.get(state)+","+tkn);
				}
				else
				{
					component_hash.put(state, component_hash.get(state)+tkn);
				}
				prestate=state;
				if(outputs[0].toLowerCase().equals("codon"))
				{
					codon_exist=true;
				}
			}
			start_count=start_count+outputs[0].length();
		}
		PostMEfile.close();
		
		HashMap<String,String> mention2id_hash = new HashMap<String,String>();
		for(int i=0;i<count;i++)
		{
			if(!filteringNum_hash.containsKey(i) && (!identifierlist.get(i).equals("_Remove_")))
			{
				if(typelist.get(i).equals("SNP"))
				{
					String id_rev = identifierlist.get(i);
					id_rev=id_rev.replaceAll(",","");
					identifierlist.set(i, id_rev);
				}
				mention2id_hash.put(mentionlist.get(i),typelist.get(i)+"\t"+identifierlist.get(i));
			}
		}
		
		
		BufferedWriter fr = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outputfile), "UTF-8"));
		br = new BufferedReader(new InputStreamReader(new FileInputStream(inputfile), "UTF-8"));
		String mention="";
		while ((mention = br.readLine()) != null)  
		{
			fr.write(mention+"\t"+mention2id_hash.get(mention)+"\n");
		}
		br.close();
		fr.close();
	}
	
	public static void main(String [] args) throws IOException, InterruptedException, XMLStreamException, SQLException 
	{
		String InputFolder="input";
		String OutputFolder="output";
		String tmpFolder="tmp";
		String DeleteTmp="True";
		int suffixNum=-1;
		String InputFileType="list";
		if(args.length<1)
		{
			System.out.println("\n$ java -Xmx5G -Xms5G -jar ToHGVs.jar [InputFolder:input] [OutputFolder:output] [suffixNum or InputFileType]");
			System.out.println("\n$ java -Xmx5G -Xms5G -jar ToHGVs.jar input output 0");
			System.out.println("\n$ java -Xmx5G -Xms5G -jar ToHGVs.jar input output list");
		}
		else
		{
			InputFolder=args [0];
			OutputFolder=args [1];
			if(args.length>=3)
			{
				if(args[2].equals("list"))
				{
					InputFileType="list";
				}
				else
				{
					suffixNum=Integer.parseInt(args[2]);
				}
			}
		}	
			
		double startTime,endTime,totTime;
		startTime = System.currentTimeMillis();//start time
		
		// load
		{
			VariantType_hash.put("INSERT","INS");VariantType_hash.put("INSERTION","INS");VariantType_hash.put("INSERTED","INS");VariantType_hash.put("INSERTING","INS");VariantType_hash.put("DUPLICATE","DUP");VariantType_hash.put("DUPLICATION","DUP");VariantType_hash.put("DUPLICATED","DUP");VariantType_hash.put("DUPLICATING","DUP");VariantType_hash.put("DELETE","DEL");VariantType_hash.put("DELETION","DEL");VariantType_hash.put("DELETED","DEL");VariantType_hash.put("DELETING","DEL");VariantType_hash.put("INSERTION/DELETION","INDEL");VariantType_hash.put("DELETION/INSERTION","INDEL");VariantType_hash.put("INSERTIONDELETION","INDEL");VariantType_hash.put("DELETIONINSERTION","INDEL");VariantType_hash.put("DELINS","INDEL");VariantType_hash.put("LACK","DEL");VariantType_hash.put("LACKED","DEL");VariantType_hash.put("LACKING","DEL");VariantType_hash.put("LOSE","DEL");VariantType_hash.put("LOSING","DEL");VariantType_hash.put("LOSED","DEL");VariantType_hash.put("COPY","DUP");VariantType_hash.put("REPEAT","DUP");VariantType_hash.put("REPEATED","DUP");VariantType_hash.put("DELTA","DEL");VariantType_hash.put("D","DEL");			nametothree.put("GLUTAMIC","GLU");nametothree.put("ASPARTIC","ASP");nametothree.put("THYMINE", "THY");nametothree.put("ALANINE", "ALA");nametothree.put("ARGININE", "ARG");nametothree.put("ASPARAGINE", "ASN");nametothree.put("ASPARTICACID", "ASP");nametothree.put("ASPARTATE", "ASP");nametothree.put("CYSTEINE", "CYS");nametothree.put("GLUTAMINE", "GLN");nametothree.put("GLUTAMICACID", "GLU");nametothree.put("GLUTAMATE", "GLU");nametothree.put("GLYCINE", "GLY");nametothree.put("HISTIDINE", "HIS");nametothree.put("ISOLEUCINE", "ILE");nametothree.put("LEUCINE", "LEU");nametothree.put("LYSINE", "LYS");nametothree.put("METHIONINE", "MET");nametothree.put("PHENYLALANINE", "PHE");nametothree.put("PROLINE", "PRO");nametothree.put("SERINE", "SER");nametothree.put("THREONINE", "THR");nametothree.put("TRYPTOPHAN", "TRP");nametothree.put("TYROSINE", "TYR");nametothree.put("VALINE", "VAL");nametothree.put("STOP", "XAA");nametothree.put("TERM", "XAA");nametothree.put("TERMINATION", "XAA");nametothree.put("STOP", "XAA");nametothree.put("TERM", "XAA");nametothree.put("TERMINATION", "XAA");nametothree.put("GLUTAMICCODON","GLU");nametothree.put("ASPARTICCODON","ASP");nametothree.put("THYMINECODON","THY");nametothree.put("ALANINECODON","ALA");nametothree.put("ARGININECODON","ARG");nametothree.put("ASPARAGINECODON","ASN");nametothree.put("ASPARTICACIDCODON","ASP");nametothree.put("ASPARTATECODON","ASP");nametothree.put("CYSTEINECODON","CYS");nametothree.put("GLUTAMINECODON","GLN");nametothree.put("GLUTAMICACIDCODON","GLU");nametothree.put("GLUTAMATECODON","GLU");nametothree.put("GLYCINECODON","GLY");nametothree.put("HISTIDINECODON","HIS");nametothree.put("ISOLEUCINECODON","ILE");nametothree.put("LEUCINECODON","LEU");nametothree.put("LYSINECODON","LYS");nametothree.put("METHIONINECODON","MET");nametothree.put("PHENYLALANINECODON","PHE");nametothree.put("PROLINECODON","PRO");nametothree.put("SERINECODON","SER");nametothree.put("THREONINECODON","THR");nametothree.put("TRYPTOPHANCODON","TRP");nametothree.put("TYROSINECODON","TYR");nametothree.put("VALINECODON","VAL");nametothree.put("STOPCODON","XAA");nametothree.put("TERMCODON","XAA");nametothree.put("TERMINATIONCODON","XAA");nametothree.put("STOPCODON","XAA");nametothree.put("TERMCODON","XAA");nametothree.put("TERMINATIONCODON","XAA");nametothree.put("TAG","XAA");nametothree.put("TAA","XAA");nametothree.put("UAG","XAA");nametothree.put("UAA","XAA");
			threetone.put("ALA", "A");threetone.put("ARG", "R");threetone.put("ASN", "N");threetone.put("ASP", "D");threetone.put("CYS", "C");threetone.put("GLN", "Q");threetone.put("GLU", "E");threetone.put("GLY", "G");threetone.put("HIS", "H");threetone.put("ILE", "I");threetone.put("LEU", "L");threetone.put("LYS", "K");threetone.put("MET", "M");threetone.put("PHE", "F");threetone.put("PRO", "P");threetone.put("SER", "S");threetone.put("THR", "T");threetone.put("TRP", "W");threetone.put("TYR", "Y");threetone.put("VAL", "V");threetone.put("ASX", "B");threetone.put("GLX", "Z");threetone.put("XAA", "X");threetone.put("TER", "X");
			threetone_nu.put("GCU","A");threetone_nu.put("GCC","A");threetone_nu.put("GCA","A");threetone_nu.put("GCG","A");threetone_nu.put("CGU","R");threetone_nu.put("CGC","R");threetone_nu.put("CGA","R");threetone_nu.put("CGG","R");threetone_nu.put("AGA","R");threetone_nu.put("AGG","R");threetone_nu.put("AAU","N");threetone_nu.put("AAC","N");threetone_nu.put("GAU","D");threetone_nu.put("GAC","D");threetone_nu.put("UGU","C");threetone_nu.put("UGC","C");threetone_nu.put("GAA","E");threetone_nu.put("GAG","E");threetone_nu.put("CAA","Q");threetone_nu.put("CAG","Q");threetone_nu.put("GGU","G");threetone_nu.put("GGC","G");threetone_nu.put("GGA","G");threetone_nu.put("GGG","G");threetone_nu.put("CAU","H");threetone_nu.put("CAC","H");threetone_nu.put("AUU","I");threetone_nu.put("AUC","I");threetone_nu.put("AUA","I");threetone_nu.put("CUU","L");threetone_nu.put("CUC","L");threetone_nu.put("CUA","L");threetone_nu.put("CUG","L");threetone_nu.put("UUA","L");threetone_nu.put("UUG","L");threetone_nu.put("AAA","K");threetone_nu.put("AAG","K");threetone_nu.put("AUG","M");threetone_nu.put("UUU","F");threetone_nu.put("UUC","F");threetone_nu.put("CCU","P");threetone_nu.put("CCC","P");threetone_nu.put("CCA","P");threetone_nu.put("CCG","P");threetone_nu.put("UCU","S");threetone_nu.put("UCC","S");threetone_nu.put("UCA","S");threetone_nu.put("UCG","S");threetone_nu.put("AGU","S");threetone_nu.put("AGC","S");threetone_nu.put("ACU","T");threetone_nu.put("ACC","T");threetone_nu.put("ACA","T");threetone_nu.put("ACG","T");threetone_nu.put("UGG","W");threetone_nu.put("UAU","Y");threetone_nu.put("UAC","Y");threetone_nu.put("GUU","V");threetone_nu.put("GUC","V");threetone_nu.put("GUA","V");threetone_nu.put("GUG","V");threetone_nu.put("UAA","X");threetone_nu.put("UGA","X");threetone_nu.put("UAG","X");threetone_nu.put("GCT","A");threetone_nu.put("GCC","A");threetone_nu.put("GCA","A");threetone_nu.put("GCG","A");threetone_nu.put("CGT","R");threetone_nu.put("CGC","R");threetone_nu.put("CGA","R");threetone_nu.put("CGG","R");threetone_nu.put("AGA","R");threetone_nu.put("AGG","R");threetone_nu.put("AAT","N");threetone_nu.put("AAC","N");threetone_nu.put("GAT","D");threetone_nu.put("GAC","D");threetone_nu.put("TGT","C");threetone_nu.put("TGC","C");threetone_nu.put("GAA","E");threetone_nu.put("GAG","E");threetone_nu.put("CAA","Q");threetone_nu.put("CAG","Q");threetone_nu.put("GGT","G");threetone_nu.put("GGC","G");threetone_nu.put("GGA","G");threetone_nu.put("GGG","G");threetone_nu.put("CAT","H");threetone_nu.put("CAC","H");threetone_nu.put("ATT","I");threetone_nu.put("ATC","I");threetone_nu.put("ATA","I");threetone_nu.put("CTT","L");threetone_nu.put("CTC","L");threetone_nu.put("CTA","L");threetone_nu.put("CTG","L");threetone_nu.put("TTA","L");threetone_nu.put("TTG","L");threetone_nu.put("AAA","K");threetone_nu.put("AAG","K");threetone_nu.put("ATG","M");threetone_nu.put("TTT","F");threetone_nu.put("TTC","F");threetone_nu.put("CCT","P");threetone_nu.put("CCC","P");threetone_nu.put("CCA","P");threetone_nu.put("CCG","P");threetone_nu.put("TCT","S");threetone_nu.put("TCC","S");threetone_nu.put("TCA","S");threetone_nu.put("TCG","S");threetone_nu.put("AGT","S");threetone_nu.put("AGC","S");threetone_nu.put("ACT","T");threetone_nu.put("ACC","T");threetone_nu.put("ACA","T");threetone_nu.put("ACG","T");threetone_nu.put("TGG","W");threetone_nu.put("TAT","Y");threetone_nu.put("TAC","Y");threetone_nu.put("GTT","V");threetone_nu.put("GTC","V");threetone_nu.put("GTA","V");threetone_nu.put("GTG","V");threetone_nu.put("TAA","X");threetone_nu.put("TGA","X");threetone_nu.put("TAG","X");
			NTtoATCG.put("ADENINE", "A");NTtoATCG.put("CYTOSINE", "C");NTtoATCG.put("GUANINE", "G");NTtoATCG.put("URACIL", "U");NTtoATCG.put("THYMINE", "T");NTtoATCG.put("ADENOSINE", "A");NTtoATCG.put("CYTIDINE", "C");NTtoATCG.put("THYMIDINE", "T");NTtoATCG.put("GUANOSINE", "G");NTtoATCG.put("URIDINE", "U");
			Number_word2digit.put("ZERO","0");Number_word2digit.put("SINGLE","1");Number_word2digit.put("ONE","1");Number_word2digit.put("TWO","2");Number_word2digit.put("THREE","3");Number_word2digit.put("FOUR","4");Number_word2digit.put("FIVE","5");Number_word2digit.put("SIX","6");Number_word2digit.put("SEVEN","7");Number_word2digit.put("EIGHT","8");Number_word2digit.put("NINE","9");Number_word2digit.put("TWN","10");
		}
		
		File folder = new File(InputFolder);
		File[] listOfFiles = folder.listFiles();
		for (int i = 0; i < listOfFiles.length; i++)
		{
			if (listOfFiles[i].isFile()) 
			{
				String InputFile = listOfFiles[i].getName();
				
				String fileSet="";
				int fileSuffix=-1;
				Pattern ptmp = Pattern.compile("^([0-9]+)");
				Matcher mtmp = ptmp.matcher(InputFile);
				if(mtmp.find())
				{
					fileSet=mtmp.group(1);
					if(fileSet.length()>=2)
					{
						fileSet=fileSet.substring(fileSet.length()-2);
					}
					fileSuffix=Integer.parseInt(fileSet);
				}
				if(suffixNum==-1 || fileSuffix == suffixNum)
				{
					File f = new File(OutputFolder+"/"+InputFile);
					if(f.exists() && !f.isDirectory()) 
					{ 
						System.out.println(InputFile+" - Done. (The output file exists)");
					}
					else
					{
						System.out.print(InputFile+" - (Variant list format) : Processing ... \r");
						
						if(InputFileType.equals("list"))
						{
							ToPostMEData(InputFolder+"/"+InputFile,tmpFolder+"/"+InputFile);
							ToPostMEoutput(tmpFolder+"/"+InputFile+".data",tmpFolder+"/"+InputFile+".output");
							TotmVArFormList(InputFolder+"/"+InputFile,tmpFolder+"/"+InputFile+".output",tmpFolder+"/"+InputFile+".ml",OutputFolder+"/"+InputFile);
						}
						else
						{
							/*
							 * Format Check 
							 */
							String Format = "";
							String checkR=BioCFormatCheck(InputFolder+"/"+InputFile);
							if(checkR.equals("BioC"))
							{
								Format = "BioC";
							}
							else if(checkR.equals("PubTator"))
							{
								Format = "PubTator";
							}
							else
							{
								//System.out.println(InputFolder+"/"+InputFile+" : Input format is BioC-XML/PubTator only.");
								//System.exit(0);
								Format = "BioC";
							}
							
							if(checkR.equals("BioC"))
							{
								ToHGVs_BioC(InputFolder+"/"+InputFile,OutputFolder+"/"+InputFile);
							}
							else if(checkR.equals("PubTator"))
							{
								ToHGVs_PubTator(InputFolder+"/"+InputFile,OutputFolder+"/"+InputFile);
							}
						}
						
						/*
						 * Time stamp - last
						 */
						endTime = System.currentTimeMillis();//ending time
						totTime = endTime - startTime;
						System.out.println(InputFile+" - (Variant list format) : Processing Time:"+totTime/1000+"sec");
						
						
						/*
						 * remove tmp files
						 */
						if(DeleteTmp.toLowerCase().equals("true"))
						{
							File file = new File(tmpFolder);
					        File[] files = file.listFiles(); 
					        for (File ftmp:files) 
					        {
					        	if (ftmp.isFile() && ftmp.exists()) 
					            {
					        		
					        		if(ftmp.toString().matches(tmpFolder+"."+InputFile+".*"))
						        	{
					        			ftmp.delete();
						        	}
					        	}
					        }
						}
					}
				}
			}
		}
	}
}
