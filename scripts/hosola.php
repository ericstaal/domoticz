#!/usr/bin/env php

<?php

// Settings
$hosola_ip = "192.168.13.100"; // IP of hosola
$hosola_port = 8899;          // Port number
$hosola_serial = "6XXXXXXXX"; // integers only

$domoticz_url = "http://user:pwd@127.0.0.1:8080";  // Domoticz URL with passwords

$debug_log = 0;   // 0 = none, 1 = exceptions, 2 result 3 = all
$max_tries = 2;   // After 3 failed actions 0 values are send, assume the inverter went down (no sun) minimal 1
$sleeptime = 15;  // Second between each pull request

$idx_energy = 13; // Sensor ID energy
$idx_vac = 14;    // Sensor ID V AC
$idx_vdc = 15;    // Sensor ID V DC
$idx_temp = 16;   // Sensor ID temperature

$temp_max = 200;  // inverter can report large temperatures when not inverting. Limit is to this max.

// variables for the script 
$data = []; // where all vars are stored
$inverter_id = calculateIDString($hosola_serial); // id to retrieve data
$nof_tries = 0;

// All item not used are marked as comment
$mapping = [
//["field" => "header", "offset" => 0, "length" => 4, "devider" => 1],          /* unknown*/
//["field" => "generated_id_1", "offset" => 4, "length" => 4, "devider" => 1],  /* unknown*/
//["field" => "generated_id_2", "offset" => 8, "length" => 4, "devider" => 1],  /* unknown*/
//["field" => "unk_1", "offset" => 12, "length" => 4, "devider" => 1],          /* unknown*/
//["field" => "inverter_id", "offset" => 15, "length" => 16, "devider" => 1],   /* inverter_id */
["field" => "temperature", "offset" => 31, "length" => 2, "devider" => 10],   /* temperature (of the inverter)*/
["field" => "vpv1", "offset" => 33, "length" => 2, "devider" => 10],          /* voltage string 1*/
//["field" => "vpv2", "offset" => 35, "length" => 2, "devider" => 10],          /* voltage string 2*/
//["field" => "vpv3", "offset" => 37, "length" => 2, "devider" => 10],          /* voltage string 3*/
//["field" => "ipv1", "offset" => 39, "length" => 2, "devider" => 10],          /* power string 1 */
//["field" => "ipv2", "offset" => 41, "length" => 2, "devider" => 10],          /* power string 2 */
//["field" => "ipv3", "offset" => 43, "length" => 2, "devider" => 10],          /* power string 3 */
//["field" => "iac1", "offset" => 45, "length" => 2, "devider" => 10],          /* amperage of string 1 */
//["field" => "iac2", "offset" => 47, "length" => 2, "devider" => 10],          /* amperage of string 2 */
//["field" => "iac3", "offset" => 49, "length" => 2, "devider" => 10],          /* amperage of string 3 */
["field" => "vac1", "offset" => 51, "length" => 2, "devider" => 10],          /* net voltage of phase 1 */
//["field" => "vac2", "offset" => 53, "length" => 2, "devider" => 10],          /* net voltage of phase 2 */
//["field" => "vac3", "offset" => 55, "length" => 2, "devider" => 10],          /* net voltage of phase 3 */
//["field" => "fac1", "offset" => 57, "length" => 2, "devider" => 100],         /* net frequency of phase 1 */
["field" => "pac1", "offset" => 59, "length" => 2, "devider" => 1],           /* net power of phase 1 */
//["field" => "fac2", "offset" => 62, "length" => 2, "devider" => 100],         /* net frequency of phase 2 */
//["field" => "pac2", "offset" => 63, "length" => 2, "devider" => 1],           /* net power of phase 2 */
//["field" => "fac3", "offset" => 65, "length" => 2, "devider" => 100],         /* net frequency of phase 3 */
//["field" => "pac3", "offset" => 67, "length" => 2, "devider" => 1],           /* net power of phase 3 */
//["field" => "etoday", "offset" => 69, "length" => 2, "devider" => 100],       /* energy generated today */
["field" => "etotal", "offset" => 71, "length" => 4, "devider" => 10],        /* total energy generated */
//["field" => "htotal", "offset" => 75, "length" => 4, "devider" => 1],         /* total run time of the inverted */
//["field" => "unk_2", "offset" => 79, "length" => 20, "devider" => 1],         /* unknown*/
];

/* read etotal initally, since it only can increase, must be retrieved before continue */
$initalValueRetrieved = false;
while (!$initalValueRetrieved)
{
  try
  {
    $parsed_json = json_decode(file_get_contents($domoticz_url."/json.htm?type=devices&rid=".$idx_energy), true);
    if (array_key_exists('result', $parsed_json) && array_key_exists('Data', $parsed_json['result'][0]) )
    {
      $data["etotal"] = floatval ( $parsed_json['result'][0]['Data']);
      $initalValueRetrieved = true;

      if ($debug_log > 2)
      {
        print "Current total energy ". $data["etotal"]." kwh.\n";
      }
    }
  }
  catch(Exception $e) 
  {
    if ($debug_log > 0)
    {
      print 'Error while reading current total energy: ' .$e->getMessage().'\n';
    }
    sleep ($sleeptime);
  }
}

while (true)
{
  if (fetch())
  {
    if ($nof_tries > 0)
    {
      $nof_tries = 0;
    }
    sendToDomoticz();
  }
  else
  {
    $nof_tries++;
    if ($nof_tries >= $max_tries)
    {
      if ($nof_tries == $max_tries)
      {
        resetData();
      }
      sendToDomoticz();
    }
  }
  sleep($sleeptime);
}

// Conversion functions
function getLong($databuffer, $start = 71, $divider = 10)
{
  $t = floatval(str2dec(substr($databuffer, $start, 4)));
  return $t / $divider;
}

function getShort($databuffer, $start = 59, $divider = 10, $iterate = 0, $offset = 2) // return (optionally repeating) values
{
  if ($iterate == 0) // 0 = no repeat, return one value
  {
    $t = floatval(str2dec(substr($databuffer, $start, 2)));  // convert to decimal 2 bytes
    return ($t == 65535) ? 0 : $t / $divider;// if 0xFFFF return 0 else value/divder
  }
  else
  {
    $iterate = min($iterate, 3);// max iterations = 3
    for ($i = 1; $i <= $iterate; $i++)
    {
      $t = floatval(str2dec(substr($databuffer, $start + $offset * ($i - 1), 2)));  // convert two bytes from databuffer to decimal
      return ($t == 65535) ? 0 : $t / $divider;// if 0xFFFF return 0 else value/divder
    }
  }
  return false;
}

function str2dec($string) // convert string to decimal	i.e. string = 0x'0101' (=chr(1).chr(1)) => dec = 257
{
  $str = strrev($string); // reverse string 0x'121314'=> 0x'141312'
  $dec = 0; // init
  
  for ($i = 0; $i < strlen($string); $i++)// foreach byte calculate decimal value multiplied by power of 256^$i
  {
    $dec += ord(substr($str, $i, 1)) * pow(256, $i);// take a byte, get ascii value, muliply by 256^(0,1,...n where n=length-1) and add to $dec
  }
  return $dec;  // return decimal
}

function hex2str($hex) // convert readable hexstring to chracter string i.e. "41424344" => "ABCD"
{
  $string = ''; // init
  for ($i = 0; $i < strlen($hex) - 1; $i += 2)// process each pair of bytes
  {
    $string .= chr(hexdec($hex[$i] . $hex[$i + 1]));  // pick 2 bytes, convert via hexdec to chr
  }
  return $string; // return string
}

// create ID string on serial number_formatfunction calculateIDString($serial)
function calculateIDString($serial)
{
  $hexsn = dechex($serial); // convert serialnumber to hex
  $cs = 115;  // offset, not found any explanation sofar for this offset
  $tmpStr = '';
  for($i = strlen($hexsn); $i > 0; $i -= 2) // in reverse order of serial; 11223344 => 44332211 and calculate checksum
  {
    $tmpStr .= substr($hexsn, $i - 2, 2);          // create reversed string byte for byte
    $cs += 2 * ord(hex2str(substr($hexsn, $i - 2, 2)));  // multiply by 2 because of rule b and d
  }
  $checksum = hex2str(substr(dechex($cs), -2)); // convert checksum and take last byte
  // now glue all parts together : fixed part (a) + s/n twice (b) + fixed string (c) + checksum (d) + fixend ending char
  return "\x68\x02\x40\x30" . hex2str($tmpStr . $tmpStr) . "\x01\x00" . $checksum . "\x16";  // create inverter ID string
}

// Receives data from inverter and store it in data
function fetch()
{
  global $debug_log;
  global $hosola_ip;
  global $hosola_port;
  global $inverter_id;
  global $sleeptime;
  
  $ret_value = false;
  
  $error_code = null;
  $error_string = null;
  
  try
  {
    $socket = @stream_socket_client("tcp://" . $hosola_ip . ":" . $hosola_port, $error_code, $error_string, 3);
      
    if ($socket === false)
    {
      if ($debug_log > 1)
      {
        print "Unable to connect to:". $hosola_ip." port:".$hosola_port.". Error_code:".$error_code.", ".$error_string."\n";
      }
    }
    else
    {
      // socket is open send data
      $bytessent = fwrite($socket, $inverter_id, strlen($inverter_id));
      if($bytessent === false && ($debug_log > 1))
      {
        print "Unable to send identification to the inverter.\n";
      }
      else
      {
        $databuffer = @fread($socket, 128);
        if($databuffer !== false)
        {
          $bytesreceived = strlen($databuffer);
          if($bytesreceived > 90)
          {
            $ret_value = parseData($databuffer);
          }
          else
          {
            // If we poll too much we may get "no inverter data" or something like that. When waiting some additional time it is solved
            sleep ($sleeptime);
            if ($debug_log > 1)
            {
              print "Incorrect data length, expected 99 bytes but received ". $bytesreceived." bytes.\n";
            }
          }
        }
        else
        {
          if ($debug_log > 1)
          {
            print "No data received from device.\n";
          }
        }
      }
      fclose($socket);
    }
  }
  catch(Exception $e) 
  {
    if ($debug_log > 0)
    {
      print 'Error while fetching: ' .$e->getMessage().'\n';
    }
  }

  return $ret_value;
}

// convert data to map     
function parseData($databuffer)
{
  global $debug_log;
  global $data;
  global $mapping;
  global $temp_max;
  
  $ret_value = false;
  
  try
  {
    foreach($mapping as $key => $element)
    {
      $value = null;
      if($element["length"] > 2)
      {
        $value = getLong($databuffer, $element["offset"], $element["devider"]);
      }
      else
      {
        $value = getShort($databuffer, $element["offset"], $element["devider"]);
      }
      $data[$element["field"]] = $value;
    }
    
    // limit temperature 
    if ((array_key_exists('temperature', $data)) && ($data['temperature'] > $temp_max))
    {
      $data['temperature'] = $temp_max;
    }      
    
    $ret_value = true;
  }
  catch(Exception $e) 
  {
    if ($debug_log > 0)
    {
      print 'Error while parsing: ' .$e->getMessage().'\n';
    }
  }
  return $ret_value;
}  

// reset data to default
function resetData()
{
  global $debug_log;
  global $data;
  global $lastsenddata;
  global $mapping;
  $ret_value = false;
  
  try
  {
    foreach($mapping as $key => $element)
    {
      if ('etotal' != $element["field"]) /* keep etotal */
      {
        $data[$element["field"]] = 0;
      }
    }
    $ret_value = true;
  }
  catch(Exception $e) 
  {
    if ($debug_log > 0)
    {
      print 'Error while resetting: ' .$e->getMessage().'\n';
    }
  }
  return $ret_value;
}  

// send json command
function sendJSON($url)
{
  global $debug_log;
    
  $ret_value = false;
  try
  {
    $reply = json_decode(file_get_contents($url), true);
    $ret_value =  ($reply['status'] == 'OK');
    
    if (($debug_log > 1) && (!$ret_value) )
    {
      print "Failed sending: ". $url.". Result:\n";
      print_r($reply);
    }
  }
  catch (Exception $e)
  {
    if ($debug_log)
    {
      print 'Error while sending url('.$url.') : ' .$e->getMessage().'\n';
    }
  }
  return $ret_value;
  
}

function updateParameter($param, $idx, $secondparam = "none", $secondfactor = 1000 )
{
  global $debug_log;
  global $data;
  global $domoticz_url;
   
  try
  {
    if (array_key_exists($param, $data))
    {
      if ($secondparam == "none")
      {
        sendJSON($domoticz_url.'/json.htm?type=command&param=udevice&idx='.$idx.'&nvalue=0&svalue='.$data[$param]);
      }
      else
      {
        sendJSON($domoticz_url.'/json.htm?type=command&param=udevice&idx='.$idx.'&nvalue=0&svalue='.$data[$param].';'.($data[$secondparam]*$secondfactor));
      }
    }
    else
    {
      if ($debug_log > 1)
      {
        print 'Parameter: '.$param.' does not exists.\n';
      }
    }
  }
  catch (Exception $e) 
  {
    if ($debug_log > 0)
    {
      print 'Error while updateParameter: ' .$e->getMessage().'\n';
    }
  }
}

// send to domticz
function sendToDomoticz()
{
  global $debug_log;
  global $idx_temp;
  global $idx_vdc;
  global $idx_vac;
  global $idx_energy;
    
  try
  {
    updateParameter('temperature', $idx_temp);
    updateParameter('vpv1', $idx_vdc);
    updateParameter('vac1', $idx_vac);
    updateParameter('pac1', $idx_energy, 'etotal', 1000);
  }
  catch (Exception $e) 
  {
    if ($debug_log > 0)
    {
      print 'Error while sendToDomoticz: ' .$e->getMessage().'\n';
    }
  }
}
?>

