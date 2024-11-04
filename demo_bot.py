from botocore.client import Config
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import discord
import aiohttp
import asyncio
import aioboto3
import re
import os
load_dotenv()

secret = os.getenv("pass")
host_email = os.getenv("host_email")
user_email = os.getenv("user_email")
api = os.getenv("discord_demo_bot")
bucket = os.getenv("bucket")
region = os.getenv("region")
aws_access_key = os.getenv("ACCESS")
aws_secret_key = os.getenv("SECACCESS")


MY_GUILD = discord.Object(id=#Your Guild ID)
# Used disocrd docs to update sync
class client(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents = intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)

intents = discord.Intents.default()
aclient = client(intents=intents)

@aclient.event
async def on_ready():
    print(f'Loggined in as {aclient.user} (ID: {aclient.user.id})')
    print('------')


def remove_letters(lst, word):
    """
    Removes all occurrences of a word from each string in a list

    Args:
        lst (list): List of strings to modify
        word (str): The word to remove from each string.

    Returns:
        list: A new list with the word removed from each string
    
    """
    return [re.sub(word, "", s)for s in lst]

async def get_demo():
    """
    Retrieve demo files from DaT Host's API.

    Returns:
        list: A list of demo filenames if found
    """

    url = "https://dathost.net/api/0.1/game-servers/Your Game server ID/files/"
    headers = {"Account-Email": host_email, "content-type": "multipart/form-data; boundary=---011000010111000001101001"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, auth=aiohttp.BasicAuth(user_email,secret)) as response:
            if response.status != 200:
                print(f"Failed to retrieve files: {response.status}")
                return 

            data = await response.json()

            l = [tuple(l.values()) for l in data]
            match_demos = ([(x,y,z) for x, y,z in l if ".dem" in x])

            demos = []
            for i in match_demos:
                matches = i[0]
                demos.append(matches)
            word = "MatchZy/"

            match_demo = remove_letters(demos, word)
            return match_demo

async def download_demo(latest_demo):
    """
    Download a specific file to the local server.

    Args:
        latest_demo (str): The name of the demo file to download
    """
    download_url = f"https://dathost.net/api/0.1/game-servers/Your Game Server ID/files/MatchZy/{latest_demo}"
    headers = {"Account-Email": host_email, "content-type": "multipart/form-data; boundary=---011000010111000001101001"}
    print(latest_demo)
    async with aiohttp.ClientSession() as session:
        async with session.get(download_url, headers=headers, auth=aiohttp.BasicAuth(user_email,secret)) as download_response:
            if download_response.status != 200:
                print(f"Failed to download {latest_demo}: {download_response.status}")
                return 
                        
            content = await download_response.read()
            with open(latest_demo, mode="wb") as file:
                file.write(content)
        print(f"Demo file {latest_demo} has been retreived...")


async def upload_file(file, bucket,expiration=25200):
    """
    Upload a file to an S3 bucket and generate a presigned download URL.

    Args:
        file (str): The path of the file to upload
        bucket (str): The name of the S3 bucket
        expiration (int): Time in seconds the presigned url will remain valid '25200 seconds = 7 Hours'
    
    Returns:
        str: The presigned URL if the upload was successful.
    """

    session = aioboto3.Session()
    async with session.client('s3', aws_access_key_id=aws_access_key,
                             aws_secret_access_key=aws_secret_key, 
                             region_name=region, 
                             config=Config(signature_version='s3v4')) as s3_client:
        try:
            await s3_client.upload_file(file, bucket,os.path.basename(file))
            url = await s3_client.generate_presigned_url('get_object',Params={"Bucket": bucket, 
                                                                    "Key": os.path.basename(file)},
                                                                    ExpiresIn=expiration)
            return url
        except Exception as e:
            print(f"Error upload file to S3 bucket: {e}")


class DemoSelect(discord.ui.Select):
    """(https://gist.github.com/lykn/a2b68cb790d6dad8ecff75b2aa450f23) This was used to create drop down"""
    def __init__(self, demos):
        options = [discord.SelectOption(label=demo, value=demo) for demo in demos]
        super().__init__(placeholder="Select a demo file...", options=options)

    async def callback(self, interaction: discord.Interaction):
        """ This gets the value selected and initates the use of download demo and upload files """
        selected_demo = self.values[0]  # Get the selected demo
        await interaction.response.send_message(f"You selected: {selected_demo}", ephemeral=True)
        
        # This downloads the demo to the server then uploads it to s3 using the upload_files function
        await download_demo(selected_demo)
        await self.upload_files(interaction.channel)
    
    async def upload_files(self, channel):
        """Uploads files to S3 bucket and sends the download link"""
        path = r'/your/filepath/something'
        ext = ".dem"
        res = [file for file in os.listdir(path) if file.endswith(ext)]

        if not res:
            await channel.send("No demo files found for upload.")
            return

        await channel.send("Uploading files, please wait...")

        for r in res:
            file_path = os.path.join(path, r)
            s3_url = await upload_file(file_path, bucket)

            if os.path.exists(file_path):
                os.remove(file_path)

            if s3_url:
                embed = discord.Embed(title="Demo File", description=f"[{r}]({s3_url})")
                await channel.send(embed=embed)
            else:
                await channel.send(f"Failed to upload {r} to S3")

        await channel.send("Finished uploading files.")

class SelectView(discord.ui.View):
    """This displays the dropdown"""
    def __init__(self, demos,*, timeout = 180):
        super().__init__(timeout=timeout)
        self.add_item(DemoSelect(demos))
                  

@aclient.tree.command(name="demo", description="Gets demos")
@app_commands.checks.cooldown(1, 100, key=lambda i: (i.user.id))
@app_commands.checks.has_role("Make sure user has role to run command.")
async def demo(interaction: discord.Interaction):
    """Slash command that retrieves and displays demo files"""
    try:
        await interaction.response.send_message("Retrieving demo files... Please wait :)", ephemeral=True)
        demos =  await get_demo()
        
        view = SelectView(demos)

        await interaction.followup.send("Select a file...", view=view, ephemeral=True)

        if not demos:
            await interaction.response.send_message("No demo files found.")
            return

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

@aclient.tree.command(name="deletedemos", description="Deletes all the bots messages")
@app_commands.checks.has_role("Make sure user has role to run command.")
async def delete_demos(interaction: discord.Interaction):

    await interaction.response.send_message("Deleting bot messages please wait...", ephemeral=True)

    deleted = 0

    async for message in interaction.channel.history(limit=100):
        if message.author == aclient.user:
            await message.delete()
            await asyncio.sleep(2)
            deleted += 1
            print("Deleted messages.")
    if deleted > 0:
        await interaction.followup.send(f"deleted {deleted} messages", ephemeral=True)
    else:
        await interaction.followup.send("No messages found", ephemeral=True)

@aclient.tree.error
async def on_app_command_error(interaction:discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = '**Still on cooldown**, please try again in {:.2f}s'.format(error.retry_after)
        await interaction.response.send_message(msg, ephemeral=True)
      
    
if __name__ == "__main__":
    aclient.run(api)